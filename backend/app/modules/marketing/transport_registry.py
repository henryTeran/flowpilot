"""Trusted local credential resolution and intent-bound reconciliation references."""
import json
import os
import re
from datetime import timedelta
from typing import Literal
from pydantic import AwareDatetime, model_validator
from app.core.config import settings
from app.modules.crm.metrics import Fact, Identifier
from app.modules.marketing import dispatch_intents, dispatch_outcomes, provider, transports
from app.shared.exceptions import business_error
from app.shared.time import utcnow

class CredentialBinding(Fact):
    institute_id: Identifier
    provider: Literal["resend", "twilio", "fcm"]
    account_id: provider.Exact
    mode: Literal["live"]
    secret_env: str
    expires_at_env: str | None

    @model_validator(mode="after")
    def dedicated_environment(self):
        for name in (self.secret_env, self.expires_at_env):
            if name is not None and not re.fullmatch(r"FLOWPILOT_MARKETING_[A-Z0-9_]{1,120}", name):
                raise ValueError("Dedicated marketing environment reference required")
        if (self.provider == "fcm") != (self.expires_at_env is not None):
            raise ValueError("FCM requires a cached OAuth token expiry reference")
        if self.secret_env == self.expires_at_env: raise ValueError("Credential and expiry references must differ")
        if self.account_id != self.account_id.strip(): raise ValueError("Exact configured account identifier required")
        return self

class Expiry(Fact):
    expires_at: AwareDatetime

def catalog():
    try:
        raw = json.loads(settings.MARKETING_CREDENTIAL_BINDINGS_JSON)
        if not isinstance(raw, list): raise ValueError("Credential bindings must be a list")
        values = [CredentialBinding.model_validate(value) for value in raw]
        scopes = [(v.institute_id, v.provider, v.account_id, v.mode) for v in values]
        if len(scopes) != len(set(scopes)): raise ValueError("Ambiguous credential bindings")
        return values
    except (ValueError, TypeError):
        raise business_error("Marketing credential binding configuration is invalid") from None

def resolver(session_factory, transport=None, environment=None, timeout=10.0):
    """Local resolver only; no OAuth acquisition, provider I/O or activation.

    Environment is server-controlled. Reference reads occur inside adapter reconcile,
    after the worker has released its institute transaction, under a fresh session.
    """
    env = os.environ if environment is None else environment
    validated = transports.Https(timeout)
    client = validated if transport is None else transport
    def resolve(account):
        account = provider.Account.model_validate(account.model_dump())
        scope = (account.institute_id, account.provider, account.account_id, account.mode)
        selected = [v for v in catalog() if (v.institute_id, v.provider, v.account_id, v.mode) == scope]
        if len(selected) != 1: raise business_error("No exact marketing credential binding configured")
        binding = selected[0]
        try:
            credential = transports.Credential(env.get(binding.secret_env))
            if binding.expires_at_env is not None:
                expires = Expiry(expires_at=env.get(binding.expires_at_env)).expires_at
                if expires <= utcnow() + timedelta(seconds=timeout + 5): raise ValueError("Cached OAuth token expires before safe call window")
        except (ValueError, TypeError):
            raise business_error("Marketing credential is absent, invalid or expired") from None
        def reference(request):
            request = provider.Submission.model_validate(request.model_dump())
            if request.account != account: raise business_error("Reconciliation account differs from binding")
            with session_factory() as db:
                intent = dispatch_intents.original(db, account.institute_id, request.idempotency_key)
                if intent is None or intent.submission != request or intent.request_fingerprint != provider.fingerprint(request):
                    raise business_error("Reconciliation terms differ from retained intent")
                outcome = dispatch_outcomes.current(db, account.institute_id, intent.id)
                return outcome.request.result.provider_message_id if outcome else None
        return transports.bind(account, credential, transport=client, reference=reference)
    return resolve
