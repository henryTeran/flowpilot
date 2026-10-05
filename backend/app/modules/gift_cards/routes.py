from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.gift_cards import service
from app.modules.gift_cards.schemas import GiftCardIssue, GiftCardIssueRead, GiftCardLookup, GiftCardRead, SettingsRead, SettingsWrite

router = APIRouter(prefix="/gift-cards/institutes/{institute_id}", tags=["gift-cards"])


def operator(institute_id: str, user=Depends(require_ticket_manager)):
    if user.get("institute_id") != institute_id:
        raise HTTPException(403, "Institut non autorise")
    actor = user.get("sub")
    if not isinstance(actor, str) or not actor.strip() or len(actor) > 160:
        raise HTTPException(403, "Identite de l'operatrice requise")
    return user


def manager(user=Depends(operator)):
    if user["role"] != "responsable_institut":
        raise HTTPException(403, "Configuration et emission reservees a la responsable")
    return user


@router.get("/settings", response_model=SettingsRead)
def settings(institute_id: str, user=Depends(operator), db: Session = Depends(get_db)):
    return service.require_settings(db, institute_id)


@router.put("/settings", response_model=SettingsRead)
def configure(institute_id: str, payload: SettingsWrite, user=Depends(manager), db: Session = Depends(get_db)):
    return service.configure_currency(db, institute_id, payload.currency, user["sub"])


@router.post("", response_model=GiftCardIssueRead)
def issue(institute_id: str, payload: GiftCardIssue, user=Depends(manager), db: Session = Depends(get_db)):
    return service.card_view(service.issue_card(db, institute_id, payload, user["sub"]), include_code=True)


@router.post("/lookup", response_model=GiftCardRead)
def lookup(institute_id: str, payload: GiftCardLookup, user=Depends(operator), db: Session = Depends(get_db)):
    return service.card_view(service.lookup_card(db, institute_id, payload.code))
