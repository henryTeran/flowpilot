"""Opt-in HTTPS adapters; no credentials, activation or automatic retries in this module."""
from dataclasses import dataclass, field
from hashlib import sha256
import base64
import http.client
import json
import math
from queue import Queue, Empty
import re
import socket
import ssl
from threading import Thread, Event
from urllib.parse import urlencode
from app.modules.marketing import provider
from app.modules.marketing.dispatch_worker import Binding
from app.shared.time import utcnow

MAX_BYTES = 65536
HOSTS = {"api.resend.com", "api.twilio.com", "fcm.googleapis.com"}

@dataclass(frozen=True)
class Credential:
    value: str = field(repr=False)
    def __post_init__(self):
        if not isinstance(self.value, str) or not 1 <= len(self.value) <= 8192 or not self.value.isascii() or any(ord(c) <= 32 or ord(c) == 127 for c in self.value):
            raise ValueError("Exact non-control secret required")

@dataclass(frozen=True)
class Reply:
    status: int
    body: bytes = field(repr=False)

class Https:
    """Fixed hosts, verified TLS, no redirects/retries/proxies; caller deadline and byte cap.

    Timed-out DNS may finish in a daemon thread, but the stop guard prevents its
    later request. Bytes already submitted cannot be retracted by timing out.
    """
    def __init__(self, timeout=10.0):
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 30: raise ValueError("Bounded transport timeout required")
        self.timeout = timeout
    def request(self, method, host, path, headers, body=b""):
        if host not in HOSTS or method not in {"POST", "GET"} or not isinstance(path, str) or not path.startswith("/") or not path.isascii() or any(ord(c) <= 32 or ord(c) == 127 for c in path):
            raise ValueError("Fixed provider endpoint required")
        if not isinstance(body, bytes) or len(body) > MAX_BYTES: raise ValueError("Bounded provider request required")
        if any(not isinstance(k, str) or not isinstance(v, str) or not k.isascii() or not v.isascii() or any(ord(c) < 32 or ord(c) == 127 for c in k + v) for k, v in headers.items()):
            raise ValueError("Exact ASCII transport headers required")
        stopped, results = Event(), Queue(maxsize=1)
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        connection = http.client.HTTPSConnection(host, timeout=self.timeout, context=context)
        def invoke():
            try:
                if stopped.is_set(): return
                connection.connect(); connection.auto_open = False
                if stopped.is_set(): return
                connection.request(method, path, body=body, headers=headers)
                response = connection.getresponse(); chunks = []; size = 0
                while not stopped.is_set():
                    part = response.read1(min(4096, MAX_BYTES + 1 - size))
                    if not part: break
                    chunks.append(part); size += len(part)
                    if size > MAX_BYTES: raise ValueError("Oversized provider response")
                if not stopped.is_set(): results.put_nowait(Reply(response.status, b"".join(chunks)))
            except Exception:
                if not stopped.is_set(): results.put_nowait(ValueError("Provider transport failed or response exceeded bounds"))
            finally: connection.close()
        Thread(target=invoke, daemon=True).start()
        try:
            result = results.get(timeout=self.timeout)
            if isinstance(result, Exception): raise result
            return result
        except Empty:
            stopped.set()
            if connection.sock is not None:
                try: connection.sock.shutdown(socket.SHUT_RDWR)
                except OSError: pass
            connection.close()
            raise TimeoutError("Provider transport deadline exceeded") from None

def json_body(reply):
    if not isinstance(reply, Reply) or type(reply.status) is not int or not 100 <= reply.status <= 599 or not isinstance(reply.body, bytes) or len(reply.body) > MAX_BYTES:
        raise ValueError("Bounded typed provider response required")
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result: raise ValueError("Duplicate provider JSON key")
            result[key] = value
        return result
    def invalid_constant(value): raise ValueError("Nonstandard provider JSON number")
    result = json.loads(reply.body.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid_constant)
    if not isinstance(result, dict): raise ValueError("Provider object response required")
    return result

class Adapter:
    def __init__(self, account, credential, transport=None, reference=None):
        self.account = provider.Account.model_validate(account.model_dump())
        if self.account.mode != "live" or not isinstance(credential, Credential): raise ValueError("Live opt-in binding and typed credential required")
        self._credential = credential
        self._transport = Https() if transport is None else transport
        self._reference = (lambda request: None) if reference is None else reference
    def checked(self, request):
        request = provider.Submission.model_validate(request.model_dump())
        if request.account != self.account: raise ValueError("Exact configured adapter account required")
        return request
    def outcome(self, request, status="unknown", reference=None):
        return provider.Result(account=self.account, idempotency_key=request.idempotency_key, request_fingerprint=provider.fingerprint(request),
            status=status, provider_message_id=reference, observed_at=utcnow())
    def destination(self, request):
        return next(c.destination for c in request.eligibility.original.declaration.communications if c.channel == self.account.channel)
    def reconcile(self, request):
        request = self.checked(request)
        # Never issue a POST to recover an unknown outcome, even inside a provider key TTL.
        return self.outcome(request, reference=self._reference(request))

class Resend(Adapter):
    def __init__(self, account, *args, **kwargs):
        super().__init__(account, *args, **kwargs)
        if (account.provider, account.channel) != ("resend", "email"): raise ValueError("Resend email binding required")
    def submit(self, request):
        request = self.checked(request); content = request.eligibility.campaign.content
        scope = [self.account.institute_id, self.account.account_id, self.account.mode, request.idempotency_key]
        key = "flowpilot-" + sha256(json.dumps(scope, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
        body = {"from": self.account.sender_id, "to": [str(self.destination(request).email)], "subject": content.subject, "text": content.body}
        reply = self._transport.request("POST", "api.resend.com", "/emails", {"Authorization": "Bearer " + self._credential.value,
            "Content-Type": "application/json", "Idempotency-Key": key}, json.dumps(body, ensure_ascii=False).encode())
        value = json_body(reply)
        if reply.status in (200, 201) and isinstance(value.get("id"), str) and re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value["id"]):
            return self.outcome(request, "accepted", value["id"])
        errors = {400: {"invalid_idempotency_key", "validation_error"}, 401: {"missing_api_key", "restricted_api_key"},
            403: {"invalid_permission", "restricted_api_key", "suspended_api_key", "validation_error"},
            422: {"invalid_attachment", "invalid_parameter", "missing_required_field", "missing_required_parameter"}}
        if value.get("name") in errors.get(reply.status, set()) and isinstance(value.get("message"), str) and value["message"] and "id" not in value:
            return self.outcome(request, "rejected")
        return self.outcome(request)
    def reconcile(self, request):
        request = self.checked(request); reference = self._reference(request)
        if reference is None: return self.outcome(request)
        if not isinstance(reference, str) or not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", reference): raise ValueError("Exact Resend reference required")
        reply = self._transport.request("GET", "api.resend.com", "/emails/" + reference, {"Authorization": "Bearer " + self._credential.value})
        value = json_body(reply); content = request.eligibility.campaign.content
        if reply.status == 200 and (value.get("id"), value.get("from"), value.get("to"), value.get("subject"), value.get("text")) == (
                reference, self.account.sender_id, [str(self.destination(request).email)], content.subject, content.body):
            return self.outcome(request, "accepted", reference)
        return self.outcome(request, reference=reference)

class Twilio(Adapter):
    def __init__(self, account, *args, **kwargs):
        super().__init__(account, *args, **kwargs)
        if (account.provider, account.channel) != ("twilio", "sms") or not re.fullmatch(r"AC[0-9a-fA-F]{32}", account.account_id): raise ValueError("Twilio SMS account SID required")
    def headers(self):
        encoded = base64.b64encode((self.account.account_id + ":" + self._credential.value).encode()).decode()
        return {"Authorization": "Basic " + encoded, "Content-Type": "application/x-www-form-urlencoded"}
    def matches(self, request, value, reference=None):
        sid = value.get("sid")
        return isinstance(sid, str) and bool(re.fullmatch(r"SM[0-9a-fA-F]{32}", sid)) and (reference is None or sid == reference) and (
            value.get("account_sid"), value.get("from"), value.get("to"), value.get("body")) == (
                self.account.account_id, self.account.sender_id, self.destination(request).phone, request.eligibility.campaign.content.body)
    def submit(self, request):
        request = self.checked(request)
        body = urlencode({"From": self.account.sender_id, "To": self.destination(request).phone, "Body": request.eligibility.campaign.content.body}).encode()
        reply = self._transport.request("POST", "api.twilio.com", f"/2010-04-01/Accounts/{self.account.account_id}/Messages.json", self.headers(), body)
        value = json_body(reply)
        if reply.status == 201 and self.matches(request, value): return self.outcome(request, "accepted", value["sid"])
        code = value.get("code")
        if reply.status in (400, 401, 403, 404) and value.get("status") == reply.status and type(code) is int and 10000 <= code <= 99999 and (
                value.get("more_info") == f"https://www.twilio.com/docs/errors/{code}" and isinstance(value.get("message"), str) and value["message"] and "sid" not in value):
            return self.outcome(request, "rejected")
        return self.outcome(request)
    def reconcile(self, request):
        request = self.checked(request); reference = self._reference(request)
        if reference is None: return self.outcome(request)
        if not isinstance(reference, str) or not re.fullmatch(r"SM[0-9a-fA-F]{32}", reference): raise ValueError("Exact Twilio message SID required")
        reply = self._transport.request("GET", "api.twilio.com", f"/2010-04-01/Accounts/{self.account.account_id}/Messages/{reference}.json", self.headers())
        value = json_body(reply)
        if reply.status == 200 and self.matches(request, value, reference): return self.outcome(request, "accepted", reference)
        return self.outcome(request, reference=reference)

class Fcm(Adapter):
    def __init__(self, account, *args, **kwargs):
        super().__init__(account, *args, **kwargs)
        if (account.provider, account.channel) != ("fcm", "push") or not re.fullmatch(r"[a-z][a-z0-9-]{0,62}", account.account_id) or account.sender_id != account.account_id:
            raise ValueError("Explicit FCM sender/project binding required")
    def submit(self, request):
        request = self.checked(request)
        body = {"message": {"token": self.destination(request).push_token, "notification": {"body": request.eligibility.campaign.content.body}}}
        reply = self._transport.request("POST", "fcm.googleapis.com", f"/v1/projects/{self.account.account_id}/messages:send",
            {"Authorization": "Bearer " + self._credential.value, "Content-Type": "application/json"}, json.dumps(body, ensure_ascii=False).encode())
        value = json_body(reply); name = value.get("name"); prefix = f"projects/{self.account.account_id}/messages/"
        if reply.status == 200 and isinstance(name, str) and re.fullmatch(re.escape(prefix) + r"[A-Za-z0-9_%:.-]+", name) and len(name) <= 240:
            return self.outcome(request, "accepted", name)
        error = value.get("error")
        codes = {400: "INVALID_ARGUMENT", 401: "UNAUTHENTICATED", 403: "PERMISSION_DENIED", 404: "NOT_FOUND"}
        if reply.status in codes and isinstance(error, dict) and type(error.get("code")) is int and (error.get("code"), error.get("status")) == (
                reply.status, codes[reply.status]) and isinstance(error.get("message"), str) and error["message"] and "name" not in value:
            return self.outcome(request, "rejected")
        return self.outcome(request)
    def reconcile(self, request):
        request = self.checked(request); reference = self._reference(request)
        prefix = f"projects/{self.account.account_id}/messages/"
        if reference is not None and (not isinstance(reference, str) or not re.fullmatch(re.escape(prefix) + r"[A-Za-z0-9_%:.-]+", reference)):
            raise ValueError("Exact known FCM project message reference required")
        return self.outcome(request, reference=reference)

def bind(account, credential, transport=None, reference=None):
    cls = {"resend": Resend, "twilio": Twilio, "fcm": Fcm}.get(account.provider)
    if cls is None: raise ValueError("Supported explicit marketing transport required")
    return Binding(account, cls(account, credential, transport=transport, reference=reference))
