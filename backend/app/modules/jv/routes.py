"""No client evidence, actor, scope, SQL or provider authority accepted."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.base import query, read_capabilities as identity
from app.modules.jv import service

router = APIRouter(prefix="/jv", tags=["jv"])


@router.post("/query", response_model=service.Response)
def analyze(body: query.Request, user=Depends(require_ticket_manager), db: Session = Depends(get_db)):
    principal = identity.signed_principal(user, user.get("institute_id"))
    return service.analyze_query(db, principal, body)
