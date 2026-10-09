from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.base.read_capabilities import signed_principal
from app.modules.copilot import customer

router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.get("/capabilities", response_model=tuple[customer.Capability, ...])
def capabilities(user=Depends(require_ticket_manager)):
    principal = signed_principal(user, user.get("institute_id"))
    customer.query.guard(principal, principal.institute_id)
    return tuple(value for value in customer.REGISTRY.values()
        if value.permission == "customer_operator" or principal.role == "responsable_institut")


@router.post("/query", response_model=customer.Response)
def query(body: customer.Request, user=Depends(require_ticket_manager), db: Session = Depends(get_db)):
    principal = signed_principal(user, user.get("institute_id"))
    return customer.read(db, principal, body)
