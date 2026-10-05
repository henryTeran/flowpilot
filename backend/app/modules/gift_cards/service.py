from datetime import timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
import secrets
from sqlalchemy import select
from app.modules.customers.repository import require_customer
from app.modules.gift_cards.models import GiftCard, GiftCardSettings
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def card_view(row, now=None, include_code=False):
    now = now or utcnow()
    status = "expired" if now >= aware(row.expires_at) else "exhausted" if row.remaining == 0 else "active"
    result = {field: getattr(row, field) for field in (
        "id", "institute_id", "currency", "initial_amount", "remaining", "customer_id", "issued_at", "expires_at"
    )} | {"status": status, "usable_amount": row.remaining if status == "active" else Decimal("0")}
    return result | {"code": row.code} if include_code else result


def require_settings(db, institute):
    row = db.get(GiftCardSettings, institute)
    if row is None:
        raise business_error("Configurer la devise des cartes cadeaux pour cet institut")
    return row


def configure_currency(db, institute, currency, actor):
    lock_institute(db, institute)
    row = db.get(GiftCardSettings, institute)
    if row:
        db.refresh(row)
        if row.currency == currency:
            return row
        if db.scalar(select(GiftCard.id).where(GiftCard.institute_id == institute)):
            raise business_error("La devise ne peut plus changer apres emission d'une carte cadeau")
        from app.modules.loyalty.models import LoyaltyEarningPolicy, LoyaltyReward
        if db.scalar(select(LoyaltyEarningPolicy.id).where(LoyaltyEarningPolicy.institute_id == institute)):
            raise business_error("La devise du programme de fidelite est deja enregistree")
        if db.scalar(select(LoyaltyReward.id).where(LoyaltyReward.institute_id == institute)):
            raise business_error("La devise des recompenses est deja enregistree")
        row.currency, row.updated_at, row.actor_id = currency, utcnow(), actor
    else:
        row = GiftCardSettings(institute_id=institute, currency=currency, updated_at=utcnow(), actor_id=actor)
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def issue_card(db, institute, payload, actor):
    lock_institute(db, institute)
    facts = payload.model_dump(exclude={"idempotency_key", "amount"}) | {"amount": format(payload.amount.quantize(Decimal("0.01")), "f")}
    fingerprint = sha256(json.dumps(facts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    existing = db.scalar(select(GiftCard).where(GiftCard.institute_id == institute,
                                               GiftCard.idempotency_key == payload.idempotency_key))
    if existing:
        if existing.creation_fingerprint != fingerprint:
            raise business_error("Cette cle appartient a une autre emission de carte cadeau")
        db.refresh(existing)
        return existing
    settings = require_settings(db, institute)
    db.refresh(settings)
    if payload.customer_id:
        require_customer(db, institute, payload.customer_id)
    now = utcnow()
    row = GiftCard(id=new_id("gift"), institute_id=institute, code=secrets.token_urlsafe(24),
        currency=settings.currency, initial_amount=payload.amount, remaining=payload.amount,
        valid_days=payload.valid_days, issued_at=now, expires_at=now + timedelta(days=payload.valid_days),
        customer_id=payload.customer_id, issuance_reason=payload.reason, idempotency_key=payload.idempotency_key,
        creation_fingerprint=fingerprint, actor_id=actor)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def lookup_card(db, institute, code):
    row = db.scalar(select(GiftCard).where(GiftCard.institute_id == institute, GiftCard.code == code))
    if row is None:
        raise not_found("Carte cadeau introuvable")
    db.refresh(row)
    return row
