from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.base.read_capabilities import signed_principal
from app.modules.copilot import query as orchestration
from app.modules.base import audit
from app.modules.waitlist.originals import fingerprint
from app.modules.copilot import preparation
from app.modules.copilot import marketing
from app.modules.copilot import reorder
from app.modules.inventory import reorders
from app.modules.base import creation_capability as creation
from app.modules.base import executions
from app.modules.base import move_capability as move
from app.modules.base.plans import guard
from app.modules.waitlist.originals import Envelope

router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.get("/capabilities", response_model=tuple[orchestration.Capability, ...])
def capabilities(user=Depends(require_ticket_manager)):
    principal = signed_principal(user, user.get("institute_id"))
    orchestration.query.guard(principal, principal.institute_id)
    with audit.trace(principal, "copilot_capabilities", {}) as span:
        result = tuple(value for value in orchestration.REGISTRY.values()
            if value.permission in {"customer_operator", "planning_operator", "inventory_operator"} or principal.role == "responsable_institut")
        span.fields["audit_response_digest"] = fingerprint([value.model_dump(mode="json") for value in result])
        return result


@router.post("/query", response_model=orchestration.Response)
def query(body: orchestration.Request, user=Depends(require_ticket_manager), db: Session = Depends(get_db)):
    principal = signed_principal(user, user.get("institute_id"))
    return orchestration.read(db, principal, body)


@router.get("/preparation-capabilities", response_model=tuple[preparation.Capability | marketing.Capability | reorder.Capability, ...])
def preparation_capabilities(user=Depends(require_ticket_manager)):
    principal = signed_principal(user, user.get("institute_id"))
    guard(principal, principal.institute_id)
    with audit.trace(principal, "copilot_preparation_capabilities", {}) as span:
        result = (preparation.Capability(), preparation.Capability(name="APPOINTMENT_MOVE",
            input_schema=preparation.MoveRequest.model_json_schema(),
            preview_input_schema=preparation.MovePreviewRequest.model_json_schema()), marketing.Capability(), reorder.Capability())
        span.fields["audit_response_digest"] = fingerprint([value.model_dump(mode="json") for value in result])
        return result


@router.post("/prepare-preview", response_model=creation.Preview)
def prepare_preview(body: preparation.PreviewRequest, user=Depends(require_ticket_manager), db: Session = Depends(get_db)):
    return preparation.preview(db, signed_principal(user, user.get("institute_id")), body)


@router.post("/prepare-preview/move", response_model=move.Preview)
def move_preview(body: preparation.MovePreviewRequest, user=Depends(require_ticket_manager), db: Session = Depends(get_db)):
    return preparation.preview_move(db, signed_principal(user, user.get("institute_id")), body)


@router.post("/prepare", response_model=Envelope)
def prepare(body: preparation.Request, user=Depends(require_ticket_manager), db: Session = Depends(get_db)):
    return preparation.prepare(db, signed_principal(user, user.get("institute_id")), body)


@router.post("/prepare-preview/marketing", response_model=marketing.Preview)
def marketing_preview(body: marketing.PreviewRequest, user=Depends(require_ticket_manager), db: Session = Depends(get_db)):
    return marketing.preview(db, signed_principal(user, user.get("institute_id")), body)


@router.post("/prepare/marketing", response_model=marketing.Draft)
def marketing_prepare(body: marketing.Request, user=Depends(require_ticket_manager), db: Session = Depends(get_db)):
    return marketing.prepare(db, signed_principal(user, user.get("institute_id")), body)


@router.get("/execution-capabilities", response_model=tuple[executions.Capability, ...])
def execution_capabilities(user=Depends(require_ticket_manager)):
    principal = signed_principal(user, user.get("institute_id"))
    guard(principal, principal.institute_id)
    with audit.trace(principal, "copilot_execution_capabilities", {}) as span:
        result = (executions.REGISTRY["APPOINTMENT_CREATE"], executions.REGISTRY["APPOINTMENT_MOVE"])
        span.fields["audit_response_digest"] = fingerprint([value.model_dump(mode="json") for value in result])
        return result


@router.post("/prepare-preview/reorder", response_model=reorders.Preview)
def reorder_preview(body: reorder.PreviewRequest, user=Depends(require_ticket_manager), db: Session = Depends(get_db)):
    return reorder.preview(db, signed_principal(user, user.get("institute_id")), body)


@router.post("/prepare/reorder", response_model=reorders.Receipt)
def reorder_prepare(body: reorder.Request, user=Depends(require_ticket_manager), db: Session = Depends(get_db)):
    return reorder.prepare(db, signed_principal(user, user.get("institute_id")), body)


@router.get("/reorder-proposal-by-key", response_model=reorders.Receipt | None)
def reorder_by_key(key: str, user=Depends(require_ticket_manager), db: Session = Depends(get_db)):
    principal = signed_principal(user, user.get("institute_id"))
    guard(principal, principal.institute_id)
    with audit.trace(principal, "copilot_reorder_recover", {"key": key}) as span:
        result = reorders.original(db, principal.institute_id, key)
        span.result("recovered" if result is not None else "absent", "STOCK_REORDER_PROPOSAL",
            result.fingerprint if result is not None else None)
        return result


@router.get("/reorder-proposals/{identifier}", response_model=reorders.Receipt)
def reorder_original(identifier: str, user=Depends(require_ticket_manager), db: Session = Depends(get_db)):
    principal = signed_principal(user, user.get("institute_id"))
    guard(principal, principal.institute_id)
    with audit.trace(principal, "copilot_reorder_recover", {"identifier":identifier}) as span:
        result = reorders.require(db, principal.institute_id, identifier)
        span.result("recovered", "STOCK_REORDER_PROPOSAL", result.fingerprint)
        return result


@router.post("/execute", response_model=Envelope)
def execute(body: executions.Request, user=Depends(require_ticket_manager), db: Session = Depends(get_db)):
    return preparation.execute(db, signed_principal(user, user.get("institute_id")), body)
