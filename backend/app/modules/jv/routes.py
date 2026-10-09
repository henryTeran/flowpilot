"""No client evidence, actor, scope, SQL or provider authority accepted."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.base import query, read_capabilities as identity
from app.modules.jv import service
from app.modules.jv import scoring
from app.modules.jv import economics
from app.modules.optimizer import sources as optimizer_sources
from app.modules.optimizer.routes import manager
from fastapi import HTTPException

router = APIRouter(prefix="/jv", tags=["jv"])


@router.post("/query", response_model=service.Response)
def analyze(body: query.Request, user=Depends(require_ticket_manager), db: Session = Depends(get_db)):
    principal = identity.signed_principal(user, user.get("institute_id"))
    return service.analyze_query(db, principal, body)


@router.post("/institutes/{institute_id}/optimization", response_model=scoring.Response)
def optimization(institute_id: str, body: optimizer_sources.Request,
                 user=Depends(manager), db: Session = Depends(get_db)):
    source = optimizer_sources.read(db, institute_id, body)
    try:
        analysis = scoring.analyze(source)
    except ValueError as error:
        raise HTTPException(503, "JV optimizer evidence invalid") from error
    return scoring.Response(source=source, analysis=analysis)


@router.post("/institutes/{institute_id}/billing-comparison", response_model=economics.Response)
def billing_comparison(institute_id: str, body: economics.Request,
                       user=Depends(manager), db: Session = Depends(get_db)):
    return economics.read(db, institute_id, body)
