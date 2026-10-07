"""Historical catalog references, distinct from an agreed quote or paid price."""
from datetime import timezone
from hashlib import sha256
import json
from sqlalchemy import select
from app.modules.services.models import Service
from app.modules.gift_cards.models import GiftCardSettings
from app.shared.money import amount_fact
from app.shared.time import explicit_utc_instant


def fingerprint(terms):
    return sha256(json.dumps(terms, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")).hexdigest()


def capture(db, appointment, event_id, event_type, at, actor):
    service = db.scalar(select(Service).where(Service.id == appointment.service_id).execution_options(populate_existing=True))
    settings = db.scalar(select(GiftCardSettings).where(GiftCardSettings.institute_id == appointment.institute_id)
        .execution_options(populate_existing=True))
    member, member_quality = amount_fact(service.price_member)
    passage, passage_quality = amount_fact(service.price_passage)
    settings_at = explicit_utc_instant(settings.updated_at) if settings else None
    currency_reason = "settings_absent" if settings is None else "settings_clock_missing" if settings_at is None \
        else "future_settings" if settings_at > at else None
    terms = dict(institute_id=appointment.institute_id, appointment_id=appointment.id, event_id=event_id,
        event_type=event_type, occurred_at=at.astimezone(timezone.utc).isoformat(), actor_id=actor,
        service_id=service.id, duration_min=service.duration_min, duration_max=service.duration_max,
        currency=settings.currency if settings and currency_reason is None and settings.currency in {"CHF", "EUR"} else None,
        currency_settings_at=settings_at.astimezone(timezone.utc).isoformat() if settings_at else None,
        currency_settings_actor_id=settings.actor_id if settings else None, currency_unavailable_reason=currency_reason,
        member_minor=member, member_quality=member_quality, passage_minor=passage, passage_quality=passage_quality,
        basis="catalog_reference_at_booking_service_selection", agreed_quote=False, paid_price=False)
    return dict(terms=terms, fingerprint=fingerprint(terms))
