"""Exact stock ledger; all mutations serialize on the institute, never infer units."""
from decimal import Decimal
from sqlalchemy import func, select
from app.modules.inventory.models import StockItem, StockMovement
from app.modules.inventory.schemas import ItemRead, MovementRead
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow

MAX_MILLI = 999999999999999


def milli(quantity, unit):
    value = int(quantity * 1000)
    if unit == "unit" and value % 1000:
        raise business_error("Les articles comptes en unites exigent une quantite entiere")
    return value


def require_item(db, institute_id, item_id):
    item = db.scalar(select(StockItem).where(StockItem.id == item_id, StockItem.institute_id == institute_id))
    if item is None:
        raise not_found("Article de stock introuvable")
    return item


def balance_milli(db, institute_id, item_id):
    return int(db.scalar(select(func.coalesce(func.sum(StockMovement.quantity_milli), 0)).where(
        StockMovement.institute_id == institute_id, StockMovement.item_id == item_id)))


def read_item(item, balance):
    return ItemRead(id=item.id, institute_id=item.institute_id, sku=item.sku, name=item.name,
        category=item.category, unit=item.unit, reorder_threshold=Decimal(item.reorder_milli) / 1000,
        on_hand=Decimal(balance) / 1000, at_or_below_threshold=balance <= item.reorder_milli,
        actor_id=item.actor_id, created_at=item.created_at)


def read_movement(row, unit):
    return MovementRead(id=row.id, institute_id=row.institute_id, item_id=row.item_id,
        kind=row.kind, consumption_id=row.consumption_id, quantity=Decimal(row.quantity_milli) / 1000, unit=unit,
        reason=row.reason, actor_id=row.actor_id, idempotency_key=row.idempotency_key,
        occurred_at=row.occurred_at)


def create_item(db, institute_id, payload, actor):
    lock_institute(db, institute_id)
    threshold = milli(payload.reorder_threshold, payload.unit)
    old = db.scalar(select(StockItem).where(StockItem.institute_id == institute_id,
                                          StockItem.idempotency_key == payload.idempotency_key))
    terms = (payload.sku, payload.name, payload.category, payload.unit, threshold, payload.reason, actor)
    if old:
        if (old.sku, old.name, old.category, old.unit, old.reorder_milli, old.reason, old.actor_id) != terms:
            raise business_error("La cle de creation conserve les conditions originales")
        return read_item(old, balance_milli(db, institute_id, old.id))
    if db.scalar(select(StockItem.id).where(StockItem.institute_id == institute_id, StockItem.sku == payload.sku)):
        raise business_error("Cette reference existe deja dans cet institut")
    row = StockItem(id=new_id(), institute_id=institute_id, sku=payload.sku, name=payload.name,
        category=payload.category, unit=payload.unit, reorder_milli=threshold,
        reason=payload.reason, actor_id=actor, idempotency_key=payload.idempotency_key, created_at=utcnow())
    db.add(row)
    db.commit()
    db.refresh(row)
    return read_item(row, 0)


def move(db, institute_id, item_id, payload, actor):
    lock_institute(db, institute_id)
    item = require_item(db, institute_id, item_id)
    delta = milli(payload.quantity, item.unit)
    old = db.scalar(select(StockMovement).where(StockMovement.institute_id == institute_id,
                                              StockMovement.idempotency_key == payload.idempotency_key))
    if old:
        if (old.item_id, old.kind, old.quantity_milli, old.reason, old.actor_id) != (item_id, payload.kind, delta, payload.reason, actor):
            raise business_error("La cle de mouvement conserve les conditions originales")
        return read_movement(old, item.unit)
    if not delta or (payload.kind == "receipt" and delta < 0):
        raise business_error("Mouvement non nul requis; une entree doit etre positive")
    balance = balance_milli(db, institute_id, item_id) + delta
    if not 0 <= balance <= MAX_MILLI:
        raise business_error("Le mouvement depasse le stock disponible ou la capacite maximale")
    row = StockMovement(id=new_id(), institute_id=institute_id, item_id=item_id,
        kind=payload.kind, quantity_milli=delta, reason=payload.reason, actor_id=actor,
        idempotency_key=payload.idempotency_key, occurred_at=utcnow())
    db.add(row)
    db.commit()
    db.refresh(row)
    return read_movement(row, item.unit)


def list_items(db, institute_id, limit, offset):
    lock_institute(db, institute_id)
    items = db.scalars(select(StockItem).where(StockItem.institute_id == institute_id)
        .order_by(StockItem.sku, StockItem.id).limit(limit).offset(offset)).all()
    ids = [item.id for item in items]
    balances = dict(db.execute(select(StockMovement.item_id, func.sum(StockMovement.quantity_milli)).where(
        StockMovement.institute_id == institute_id, StockMovement.item_id.in_(ids)).group_by(StockMovement.item_id)).all()) if ids else {}
    return [read_item(item, int(balances.get(item.id, 0))) for item in items]
