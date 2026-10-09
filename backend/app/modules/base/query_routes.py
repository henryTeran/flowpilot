from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.base import query, read_capabilities as identity

router = APIRouter(prefix="/base", tags=["base"])


def provider():
    """No concrete provider yet; injection seam for provider-independent tests."""
    return None


@router.get("/query-capabilities", response_model=tuple[query.Capability, ...])
def capabilities(user=Depends(require_ticket_manager)):
    principal = identity.signed_principal(user, user.get("institute_id"))
    query.guard(principal, principal.institute_id)
    return tuple(query.REGISTRY.values())


@router.post("/query", response_model=query.Response)
def post_query(body: query.Request, user=Depends(require_ticket_manager),
               db: Session = Depends(get_db), interpreter=Depends(provider)):
    principal = identity.signed_principal(user, user.get("institute_id"))
    return query.query(db, principal, principal.institute_id, body, provider=interpreter)
