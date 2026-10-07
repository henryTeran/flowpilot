import json
from threading import Event
import time
from urllib.parse import parse_qs
import pytest
from app.modules.marketing import provider, transports
from test_marketing_provider_13ag import submission

EMAIL_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
SID = "SM" + "a" * 32

class Wire:
    def __init__(self, value, status=200): self.reply = transports.Reply(status, json.dumps(value).encode()); self.calls = []
    def request(self, *args): self.calls.append(args); return self.reply

def request(channel):
    source = submission(channel)
    account = provider.Account(institute_id="i", provider={"email": "resend", "sms": "twilio", "push": "fcm"}[channel], account_id="AC" + "b" * 32 if channel == "sms" else "project" if channel == "push" else "email-account",
        channel=channel, sender_id="project" if channel == "push" else "+41790000000" if channel == "sms" else "sender@example.com", mode="live",
        push_application="institute-app" if channel == "push" else None)
    return provider.Submission(**{**source.model_dump(), "account": account})

def response(request):
    if request.account.channel == "email": return {"id": EMAIL_ID}
    if request.account.channel == "sms": return {"sid": SID, "account_sid": request.account.account_id, "from": request.account.sender_id,
        "to": request.eligibility.original.declaration.communications[1].destination.phone, "body": request.eligibility.campaign.content.body, "status": "queued"}
    return {"name": "projects/project/messages/0:123%abc"}

@pytest.mark.parametrize("channel", ["email", "sms", "push"])
def test_adapters_preserve_exact_approved_wire_terms_and_accept_only_scoped_references(channel, monkeypatch):
    req = request(channel); wire = Wire(response(req), 201 if channel == "sms" else 200)
    binding = transports.bind(req.account, transports.Credential("fixture-secret"), transport=wire)
    result = provider.validate_result(req, binding.adapter.submit(req))
    assert result.status == "accepted" and not result.delivery_confirmed
    method, host, path, headers, body = wire.calls[0]
    assert method == "POST" and host in transports.HOSTS
    if channel == "sms":
        assert parse_qs(body.decode()) == {"From": [req.account.sender_id], "To": ["+41791234567"], "Body": [req.eligibility.campaign.content.body]}
        assert path == f"/2010-04-01/Accounts/{req.account.account_id}/Messages.json"
    elif channel == "email":
        assert json.loads(body) == {"from": req.account.sender_id, "to": ["customer@example.com"], "subject": req.eligibility.campaign.content.subject, "text": req.eligibility.campaign.content.body}
        assert headers["Idempotency-Key"].startswith("flowpilot-")
        binding.adapter.submit(req); assert wire.calls[-1][3]["Idempotency-Key"] == headers["Idempotency-Key"]
    else:
        assert json.loads(body) == {"message": {"token": "explicit-device-token", "notification": {"body": req.eligibility.campaign.content.body}}}
        assert path == "/v1/projects/project/messages:send"
    count = len(wire.calls)
    assert binding.adapter.reconcile(req).status == "unknown" and len(wire.calls) == count
    assert "fixture-secret" not in repr(binding) and "fixture-secret" not in repr(transports.Credential("fixture-secret"))
    altered = req.model_copy(update={"account": req.account.model_copy(update={"institute_id": "foreign"})})
    with pytest.raises(ValueError): binding.adapter.submit(altered)
    for status in (302, 409, 429, 500):
        wire.reply = transports.Reply(status, json.dumps(response(req)).encode())
        assert binding.adapter.submit(req).status == "unknown"
    wire.reply = transports.Reply(200, b'{"id":"a","id":"b"}')
    with pytest.raises(ValueError): binding.adapter.submit(req)

@pytest.mark.parametrize("channel", ["email", "sms"])
def test_known_reference_reconciliation_is_get_only_and_checks_full_message(channel):
    req = request(channel); ref = EMAIL_ID if channel == "email" else SID
    value = response(req)
    if channel == "email": value.update({"from": req.account.sender_id, "to": ["customer@example.com"], "subject": req.eligibility.campaign.content.subject, "text": req.eligibility.campaign.content.body})
    wire = Wire(value); adapter = transports.bind(req.account, transports.Credential("secret"), transport=wire, reference=lambda r: ref).adapter
    assert adapter.reconcile(req).status == "accepted" and wire.calls[-1][0] == "GET"
    value["body" if channel == "sms" else "text"] = "forged other message"
    wire.reply = transports.Reply(200, json.dumps(value).encode())
    assert adapter.reconcile(req).status == "unknown"
    wire.reply = transports.Reply(404, b'{}')
    assert adapter.reconcile(req).status == "unknown"
    assert all(call[0] == "GET" for call in wire.calls)

def test_fixed_https_limits_and_deadline_prevent_late_post_after_slow_connect(monkeypatch):
    connected, release, exited = Event(), Event(), Event(); calls = []
    class Connection:
        sock = None
        def __init__(self, *args, **kwargs): pass
        def connect(self): connected.set(); release.wait(2)
        def request(self, *args, **kwargs): calls.append(args)
        def close(self): exited.set()
    monkeypatch.setattr(transports.http.client, "HTTPSConnection", Connection)
    client = transports.Https(timeout=.05)
    with pytest.raises(TimeoutError): client.request("POST", "api.resend.com", "/emails", {}, b"{}")
    release.set(); time.sleep(.05); assert calls == []
    for host, path in [("localhost", "/emails"), ("api.resend.com", "/emails\nX")]:
        with pytest.raises(ValueError): client.request("POST", host, path, {})
    with pytest.raises(ValueError): client.request("POST", "api.resend.com", "/emails", {}, b"x" * (transports.MAX_BYTES + 1))
    with pytest.raises(ValueError): client.request("POST", "api.resend.com", "/emails", {"Authorization": "secret\nInjected"})
    with pytest.raises(ValueError): transports.json_body(transports.Reply(200, b"x" * (transports.MAX_BYTES + 1)))

def test_live_opt_in_and_provider_channel_project_binding_required():
    for channel in ("email", "sms", "push"):
        req = request(channel)
        with pytest.raises(ValueError): transports.bind(req.account.model_copy(update={"mode": "test"}), transports.Credential("secret"))
    req = request("push")
    with pytest.raises(ValueError): transports.bind(req.account.model_copy(update={"account_id": "project/../../bad"}), transports.Credential("secret"))
    for secret in ("", "a\nb", " padded ", "a\x7f", "non-ascii-\u00e9"):
        with pytest.raises(ValueError): transports.Credential(secret)

@pytest.mark.parametrize("channel", ["email", "sms", "push"])
def test_explicit_vendor_refusals_are_distinct_from_unknown_responses(channel):
    req = request(channel)
    errors = {"email": {"name": "validation_error", "message": "Invalid request"},
        "sms": {"status": 400, "code": 21211, "more_info": "https://www.twilio.com/docs/errors/21211", "message": "Invalid To"},
        "push": {"error": {"code": 400, "status": "INVALID_ARGUMENT", "message": "Invalid token"}}}
    wire = Wire(errors[channel], 400); adapter = transports.bind(req.account, transports.Credential("secret"), transport=wire).adapter
    assert adapter.submit(req).status == "rejected"
    wire.reply = transports.Reply(400, b'{"message":"unrecognized error"}')
    assert adapter.submit(req).status == "unknown"
    bad = response(req)
    if channel == "sms": bad["account_sid"] = "AC" + "c" * 32
    elif channel == "push": bad["name"] = "projects/foreign/messages/id"
    else: bad["id"] = "not-an-email-reference"
    wire.reply = transports.Reply(201 if channel == "sms" else 200, json.dumps(bad).encode())
    assert adapter.submit(req).status == "unknown"

def test_https_reads_bounded_bytes_once_without_following_redirects(monkeypatch):
    calls = []; payload = b'{"id":"ok"}'; status = 302
    class Response:
        def __init__(self): self.status = status; self.offset = 0
        def read1(self, size):
            result = payload[self.offset:self.offset + size]; self.offset += len(result); return result
    class Connection:
        sock = None
        def __init__(self, host, timeout, context):
            assert host == "api.resend.com" and timeout == 1 and context.check_hostname
            assert context.verify_mode == transports.ssl.CERT_REQUIRED
        def connect(self): pass
        def request(self, *args, **kwargs): calls.append((args, kwargs))
        def getresponse(self): return Response()
        def close(self): pass
    monkeypatch.setattr(transports.http.client, "HTTPSConnection", Connection)
    reply = transports.Https(timeout=1).request("POST", "api.resend.com", "/emails", {}, b"{}")
    assert reply.status == 302 and reply.body == payload and len(calls) == 1
    payload = b"x" * (transports.MAX_BYTES + 1); status = 200
    with pytest.raises(ValueError): transports.Https(timeout=1).request("POST", "api.resend.com", "/emails", {})
    assert len(calls) == 2

@pytest.mark.parametrize("lose_ack", [False, True])
def test_adapter_worker_pipeline_retains_ack_and_never_posts_during_unknown_recovery(client, monkeypatch, lose_ack):
    from datetime import timedelta
    from sqlalchemy.orm import Session
    import app.main as main_module
    from app.modules.marketing import dispatch_worker, dispatch_intents, dispatch_outcomes
    from test_marketing_recipient_observations_13z import setup
    from test_marketing_dispatch_intents_13ai import configure, body
    from test_ticket_workflow import _bootstrap_reference_data
    from test_crm_billing_12b import NOW
    institute, _, _ = _bootstrap_reference_data(client)
    _, approval, contact = setup(main_module.engine, institute, monkeypatch); configure(institute, monkeypatch)
    monkeypatch.setattr(dispatch_intents.settings, "MARKETING_ACCOUNTS_JSON", json.dumps([dict(institute_id=institute, provider="resend", account_id="account",
        channel="email", sender_id="sender@example.com", mode="live", push_application=None)]))
    for module in (dispatch_worker, dispatch_outcomes, transports): monkeypatch.setattr(module, "utcnow", lambda: NOW + timedelta(microseconds=5))
    with Session(main_module.engine) as db: intent = dispatch_intents.prepare(db, institute, body(approval, contact), "manager")
    wire = Wire({"id": EMAIL_ID})
    if lose_ack:
        def lost(*args): wire.calls.append(args); raise TimeoutError("simulated lost acknowledgement")
        wire.request = lost
    binding = transports.bind(intent.submission.account, transports.Credential("fixture-secret"), transport=wire)
    execution = dispatch_worker.run(lambda: Session(main_module.engine), institute, intent.id, "worker", lambda account: binding)
    assert execution.outcome.request.result.status == ("unknown" if lose_ack else "accepted") and len(wire.calls) == 1
    resumed = dispatch_worker.run(lambda: Session(main_module.engine), institute, intent.id, "worker", lambda account: binding)
    assert resumed.operation == ("reconcile_observed" if lose_ack else "terminal")
    assert resumed.outcome.request.result.status == ("unknown" if lose_ack else "accepted")
    assert len(wire.calls) == 1
