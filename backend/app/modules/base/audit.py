"""Operational correlation around BASE, not a business receipt or signature."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import logging
from functools import wraps
from inspect import signature
from fastapi.encoders import jsonable_encoder
from uuid import uuid4
from fastapi import HTTPException
from app.modules.base.read_capabilities import Principal
from app.modules.waitlist.originals import fingerprint

logger = logging.getLogger("app.modules.base.audit")
upstream_actor: ContextVar[str | None] = ContextVar("base_upstream_actor", default=None)
ROUTE_ACTIONS = frozenset({"discovery", "sensitive_discovery", "cancellation_preview", "prepare_operation",
    "recover_operation", "operation_history", "operation_detail", "decision", "recover_decision",
    "approval_state", "execution_capabilities", "execute", "recover_execution", "execution_for_operation",
    "context", "intent", "prepare", "recover", "history", "plan", "read"})


class Span:
    def __init__(self, principal, action, payload):
        self.id = str(uuid4())
        self.fields = {"audit_operation_id": self.id, "audit_actor_id": principal.actor_id,
            "audit_institute_id": principal.institute_id, "audit_action": action,
            "audit_request_digest": fingerprint(payload)}
        self.status = "completed"
        self.capability = None
        self.evidence = None

    def result(self, status, capability=None, evidence=None):
        self.status, self.capability, self.evidence = status, capability, evidence


@contextmanager
def trace(principal: Principal, action: str, payload):
    if action not in ROUTE_ACTIONS | {"query", "query_capabilities", "copilot_customer_query", "copilot_query", "copilot_capabilities", "copilot_creation_preview", "copilot_prepare", "copilot_preparation_capabilities", "copilot_execute", "copilot_execution_capabilities"}:
        raise ValueError("Unregistered BASE audit action")
    principal = Principal.model_validate(principal.model_dump())
    span = Span(principal, action, payload)
    token = upstream_actor.set(json.dumps({"operation_id": span.id,
        "actor_id": principal.actor_id, "institute_id": principal.institute_id}, separators=(",", ":")))
    logger.info("BASE interaction", extra={**span.fields, "audit_event": "attempt"})
    try:
        yield span
    except HTTPException as error:
        logger.info("BASE interaction", extra={**span.fields, "audit_event": "outcome", "audit_status": error.status_code})
        raise
    except Exception:
        logger.info("BASE interaction", extra={**span.fields, "audit_event": "outcome", "audit_status": 500})
        raise
    else:
        logger.info("BASE interaction", extra={**span.fields, "audit_event": "outcome",
            "audit_status": span.status, "audit_capability": span.capability, "audit_evidence_digest": span.evidence})
    finally:
        upstream_actor.reset(token)


def traced(action):
    """Validated FastAPI handler boundary; never records headers, DB or raw data."""
    if action not in ROUTE_ACTIONS:
        raise ValueError("Unregistered BASE audit action")
    def decorate(function):
        parameters = signature(function)
        @wraps(function)
        def invoke(*args, **kwargs):
            bound = parameters.bind(*args, **kwargs).arguments
            payload = jsonable_encoder({k: v for k, v in bound.items() if k not in {"db", "user"}})
            with trace(bound["user"], action, payload) as span:
                result = function(*args, **kwargs)
                span.fields["audit_response_digest"] = fingerprint(jsonable_encoder(result))
                span.result("completed", evidence=getattr(result, "fingerprint", None))
                return result
        invoke._base_audit_action = action
        return invoke
    return decorate
