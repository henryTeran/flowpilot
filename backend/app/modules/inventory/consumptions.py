"""Signed actual quantities once per captured performed line, in the stock ledger."""
from decimal import Decimal
from sqlalchemy import select
from app.modules.inventory.models import StockConsumption, StockServiceBasis, StockRecipeLine, StockMovement
from app.modules.inventory.schemas import ConsumptionRead, ConsumptionEntryRead, RecipeEntryRead
from app.modules.inventory.service import require_item, milli, balance_milli, lock_institute
from app.modules.planning.models import ServiceSession
from app.modules.appointments.models import Appointment
from app.shared.exceptions import not_found, business_error
from app.shared.ids import new_id
from app.shared.time import utcnow


def require_basis(db, institute, basis_id):
    basis = db.scalar(select(StockServiceBasis).where(StockServiceBasis.institute_id == institute,
                                                    StockServiceBasis.id == basis_id))
    if basis is None:
        raise not_found("Base d'execution introuvable; aucune recette historique n'est deduite")
    return basis


def expected(db, basis):
    if basis.state == "unconfigured":
        return None
    if basis.state == "disabled":
        return []
    lines = db.scalars(select(StockRecipeLine).where(StockRecipeLine.institute_id == basis.institute_id,
        StockRecipeLine.recipe_id == basis.recipe_id).order_by(StockRecipeLine.item_id)).all()
    return [RecipeEntryRead(item_id=line.item_id, unit=line.unit,
        quantity=Decimal(line.quantity_milli * basis.quantity) / 1000) for line in lines]


def snapshot(db, row):
    basis = require_basis(db, row.institute_id, row.basis_id)
    moves = db.scalars(select(StockMovement).where(StockMovement.institute_id == row.institute_id,
        StockMovement.consumption_id == row.id).order_by(StockMovement.item_id)).all()
    entries = [ConsumptionEntryRead(item_id=move.item_id, movement_id=move.id,
        quantity=Decimal(-move.quantity_milli) / 1000,
        unit=require_item(db, row.institute_id, move.item_id).unit) for move in moves]
    norm = expected(db, basis)
    terms = lambda rows: [(entry.item_id, entry.quantity, entry.unit) for entry in rows]
    return ConsumptionRead(id=row.id, institute_id=row.institute_id, basis_id=row.basis_id,
        actor_id=row.actor_id, reason=row.reason, idempotency_key=row.idempotency_key,
        entries=entries, expected_entries=norm,
        matches_norm=None if norm is None else terms(entries) == terms(norm), created_at=row.created_at)


def create(db, institute, basis_id, payload, actor):
    lock_institute(db, institute)
    old = db.scalar(select(StockConsumption).where(StockConsumption.institute_id == institute,
        StockConsumption.idempotency_key == payload.idempotency_key))
    if old:
        saved = snapshot(db, old)
        if (old.basis_id, old.actor_id, old.reason) != (basis_id, actor, payload.reason) or sorted(
            (entry.item_id, entry.quantity) for entry in saved.entries) != sorted(
            (entry.item_id, entry.quantity) for entry in payload.entries):
            raise business_error("La cle de consommation conserve les conditions originales")
        return saved
    basis = require_basis(db, institute, basis_id)
    if db.scalar(select(StockConsumption.id).where(StockConsumption.basis_id == basis.id)):
        raise business_error("Cette execution possede deja une consommation; relire la confirmation originale")
    source_model, source_id = (ServiceSession, basis.session_id) if basis.session_id else (Appointment, basis.appointment_id)
    source = db.scalar(select(source_model).where(source_model.id == source_id, source_model.institute_id == institute))
    if source is None or source.status != "completed":
        raise business_error("Terminer la prestation avant de confirmer les quantites reellement consommees")
    entries = []
    for entry in sorted(payload.entries, key=lambda entry: entry.item_id):
        item = require_item(db, institute, entry.item_id)
        amount = milli(entry.quantity, item.unit)
        if amount > balance_milli(db, institute, item.id):
            raise business_error("Stock insuffisant pour " + item.sku + "; aucune consommation n'est enregistree")
        entries.append((item.id, amount))
    row = StockConsumption(id=new_id(), institute_id=institute, basis_id=basis.id,
        actor_id=actor, reason=payload.reason, idempotency_key=payload.idempotency_key, created_at=utcnow())
    db.add(row)
    db.flush()
    for item_id, amount in entries:
        db.add(StockMovement(id=new_id(), institute_id=institute, item_id=item_id, kind="consumption",
            consumption_id=row.id, quantity_milli=-amount, actor_id=actor, reason=payload.reason,
            idempotency_key=new_id(), occurred_at=row.created_at))
    db.commit()
    db.refresh(row)
    return snapshot(db, row)
