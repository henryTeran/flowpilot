"""Official BASE routing to original stock proposal services, no purchase execution."""
from typing import Literal
from fastapi import HTTPException
from app.modules.crm.metrics import Fact
from app.modules.base import query, upstream, audit
from app.modules.base.plans import guard
from app.modules.inventory import reorders
from app.modules.waitlist.originals import Envelope


class PreviewRequest(Fact):
    message: query.Text
    ui_context: reorders.Selection


class Request(Fact):
    message: query.Text
    proposal: reorders.Request


class Capability(Fact):
    name: Literal["STOCK_REORDER_PROPOSAL"] = "STOCK_REORDER_PROPOSAL"
    level: Literal[2] = 2
    permission: Literal["signed_institute_manager"] = "signed_institute_manager"
    input_schema: dict = Request.model_json_schema()
    preview_input_schema: dict = PreviewRequest.model_json_schema()
    output_schema: dict = reorders.Receipt.model_json_schema()
    application_service: Literal["inventory.reorders.create"] = "inventory.reorders.create"
    audit: Literal["signed_scope_interaction_id_and_source_digest_no_raw_message"] = "signed_scope_interaction_id_and_source_digest_no_raw_message"
    effect: Literal["retained_reorder_proposal_no_order_contact_payment_receipt_or_stock_write"] = "retained_reorder_proposal_no_order_contact_payment_receipt_or_stock_write"


def route(message, router=None):
    if not message.strip():raise HTTPException(400, "Explicit reorder proposal request required")
    resolved = upstream.Route.model_validate((router or upstream.OfficialRouter()).resolve(message).model_dump())
    if resolved.status != "routed" or resolved.process_id != "stock-reorder-proposal":
        raise HTTPException(400, "BASE must route to the selected reorder proposal capability")


def preview(db, principal, candidate, router=None):
    principal = guard(principal, principal.institute_id)
    request = PreviewRequest.model_validate(candidate.model_dump(mode="json") if isinstance(candidate, PreviewRequest) else candidate)
    with audit.trace(principal, "copilot_reorder_preview", request.model_dump(mode="json")) as span:
        route(request.message, router)
        result = reorders.preview(db, principal.institute_id, request.ui_context)
        span.result("previewed", "STOCK_REORDER_PROPOSAL", result.state_fingerprint)
        return result


def prepare(db, principal, candidate, router=None):
    principal = guard(principal, principal.institute_id)
    request = Request.model_validate(candidate.model_dump(mode="json") if isinstance(candidate, Request) else candidate)
    with audit.trace(principal, "copilot_reorder_prepare", request.model_dump(mode="json")) as span:
        route(request.message, router)
        result = reorders.create(db, principal.institute_id, request.proposal, principal.actor_id)
        span.result("retained_proposal", "STOCK_REORDER_PROPOSAL", result.fingerprint)
        return result
