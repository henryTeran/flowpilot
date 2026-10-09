from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.base.read_capabilities import signed_principal
from app.modules.copilot import query as orchestration

router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.get("/capabilities", response_model=tuple[orchestration.Capability, ...])
def capabilities(user=Depends(require_ticket_manager)):
    principal = signed_principal(user, user.get("institute_id"))
    orchestration.query.guard(principal, principal.institute_id)
    return tuple(value for value in orchestration.REGISTRY.values()
        if value.permission in {"customer_operator", "planning_operator"} or principal.role == "responsable_institut")


@router.post("/query", response_model=orchestration.Response)
def query(body: orchestration.Request, user=Depends(require_ticket_manager), db: Session = Depends(get_db)):
    principal = signed_principal(user, user.get("institute_id"))
    return orchestration.read(db, principal, body)
