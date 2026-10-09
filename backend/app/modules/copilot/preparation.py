"""Official BASE routing to closed FlowPilot preparation adapters."""
from typing import Literal
from fastapi import HTTPException
from app.modules.crm.metrics import Fact
from app.modules.base import query, upstream, creation_capability as creation, sensitive_originals as operations, executions
from app.modules.base.plans import guard
from app.modules.base import audit


class PreviewRequest(Fact):
    message: query.Text
    ui_context: creation.Selection


class OperationRequest(operations.Request):
    capability: Literal["APPOINTMENT_CREATE"]
    selection: creation.Selection


class Request(Fact):
    message: query.Text
    operation: OperationRequest


class Capability(Fact):
    name: Literal["APPOINTMENT_CREATE"] = "APPOINTMENT_CREATE"
    level: Literal[2] = 2
    permission: Literal["signed_institute_manager"] = "signed_institute_manager"
    input_schema: dict = Request.model_json_schema()
    preview_input_schema: dict = PreviewRequest.model_json_schema()
    output_schema: dict = operations.Envelope.model_json_schema()
    application_service: Literal["base.sensitive_originals.create"] = "base.sensitive_originals.create"
    audit: Literal["signed_scope_interaction_id_and_source_digest_no_raw_message"] = "signed_scope_interaction_id_and_source_digest_no_raw_message"
    effect: Literal["retained_pending_preparation_no_approval_or_execution"] = "retained_pending_preparation_no_approval_or_execution"


def route(message, router=None):
    if not message.strip():
        raise HTTPException(400, "An explicit preparation request is required")
    resolved = upstream.Route.model_validate((router or upstream.OfficialRouter()).resolve(message).model_dump())
    if resolved.status != "routed" or resolved.process_id != "appointment-create":
        raise HTTPException(400, "BASE must route to the selected creation preparation")


def preview(db, principal, candidate, router=None):
    principal = guard(principal, principal.institute_id)
    request = PreviewRequest.model_validate(candidate.model_dump(mode="json") if isinstance(candidate, PreviewRequest) else candidate)
    with audit.trace(principal, "copilot_creation_preview", request.model_dump(mode="json")) as span:
        route(request.message, router)
        result = creation.preview(db, principal, principal.institute_id, request.ui_context)
        span.result("previewed", "APPOINTMENT_CREATE", result.state_fingerprint)
        return result


def prepare(db, principal, candidate, router=None):
    principal = guard(principal, principal.institute_id)
    request = Request.model_validate(candidate.model_dump(mode="json") if isinstance(candidate, Request) else candidate)
    with audit.trace(principal, "copilot_prepare", request.model_dump(mode="json")) as span:
        route(request.message, router)
        if request.operation.capability != "APPOINTMENT_CREATE":
            raise HTTPException(400, "Routed preparation and explicit operation must match")
        result = operations.create(db, principal, principal.institute_id, request.operation)
        span.result("prepared_pending_approval", "APPOINTMENT_CREATE", result.fingerprint)
        return result


def execute(db, principal, candidate):
    principal = guard(principal, principal.institute_id)
    request = executions.Request.model_validate(candidate.model_dump(mode="json") if isinstance(candidate, executions.Request) else candidate)
    with audit.trace(principal, "copilot_execute", request.model_dump(mode="json")) as span:
        operation = operations.Original.model_validate(operations.require(db, principal, principal.institute_id, request.operation_id).original)
        if operation.capability != "APPOINTMENT_CREATE":
            raise HTTPException(400, "Copilot execution capability is not registered")
        result = executions.execute(db, principal, principal.institute_id, request)
        span.result("executed", "APPOINTMENT_CREATE", result.fingerprint)
        return result
