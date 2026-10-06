"""Immutable manager-approved per-service stock recipes; no implicit consumption."""
from decimal import Decimal
from sqlalchemy import select
from app.modules.inventory.models import StockRecipe, StockRecipeLine
from app.modules.inventory.schemas import RecipeRead, RecipeEntryRead
from app.modules.inventory.service import require_item, milli
from app.modules.services.repository import get_service
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


def require_service(db, service_id):
    row = get_service(db, service_id)
    if row is None:
        raise not_found("Prestation introuvable")
    return row


def current(db, institute_id, service_id):
    return db.scalar(select(StockRecipe).where(StockRecipe.institute_id == institute_id,
        StockRecipe.service_id == service_id).order_by(StockRecipe.revision.desc()).limit(1))


def snapshot(db, row):
    entries = db.scalars(select(StockRecipeLine).where(StockRecipeLine.recipe_id == row.id,
        StockRecipeLine.institute_id == row.institute_id).order_by(StockRecipeLine.item_id)).all()
    return RecipeRead(id=row.id, institute_id=row.institute_id, service_id=row.service_id,
        revision=row.revision, base_revision=row.revision - 1, enabled=row.enabled,
        entries=[RecipeEntryRead(item_id=entry.item_id, quantity=Decimal(entry.quantity_milli) / 1000, unit=entry.unit) for entry in entries],
        reason=row.reason, actor_id=row.actor_id, idempotency_key=row.idempotency_key, created_at=row.created_at)


def create(db, institute_id, service_id, payload, actor):
    lock_institute(db, institute_id)
    original = db.scalar(select(StockRecipe).where(StockRecipe.institute_id == institute_id,
                                                StockRecipe.idempotency_key == payload.idempotency_key))
    if original:
        saved = snapshot(db, original)
        terms = sorted((entry.item_id, entry.quantity) for entry in payload.entries)
        if (original.service_id, original.revision - 1, original.enabled, original.reason, original.actor_id) != (service_id, payload.base_revision, payload.enabled, payload.reason, actor) or terms != sorted((entry.item_id, entry.quantity) for entry in saved.entries):
            raise business_error("La cle de recette conserve les conditions originales")
        return saved
    service = require_service(db, service_id)
    if payload.enabled and service.status != "active":
        raise business_error("Une recette active exige une prestation active")
    old = current(db, institute_id, service_id)
    if payload.base_revision != (old.revision if old else 0):
        raise business_error("La recette a change; relire la version courante avant une nouvelle demande")
    entries = []
    for entry in sorted(payload.entries, key=lambda entry: entry.item_id):
        item = require_item(db, institute_id, entry.item_id)
        entries.append((item.id, milli(entry.quantity, item.unit), item.unit))
    row = StockRecipe(id=new_id(), institute_id=institute_id, service_id=service_id,
        revision=payload.base_revision + 1, enabled=payload.enabled, reason=payload.reason,
        actor_id=actor, idempotency_key=payload.idempotency_key, created_at=utcnow())
    db.add(row)
    db.flush()  # Header and every original line still commit in one transaction.
    for item_id, quantity, unit in entries:
        db.add(StockRecipeLine(recipe_id=row.id, institute_id=institute_id, item_id=item_id,
                              quantity_milli=quantity, unit=unit))
    db.commit()
    db.refresh(row)
    return snapshot(db, row)
