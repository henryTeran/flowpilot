"""Institute-scoped original supplier identities for purchase-order provenance."""
from sqlalchemy import select
from app.modules.inventory.models import StockSupplier
from app.modules.inventory.schemas import SupplierRead
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


def snapshot(row):
    return SupplierRead.model_validate(row)


def require_supplier(db, institute, identifier):
    row = db.scalar(select(StockSupplier).where(StockSupplier.institute_id == institute, StockSupplier.id == identifier))
    if row is None:
        raise not_found("Fournisseur introuvable")
    return row


def create(db, institute, payload, actor):
    lock_institute(db, institute)
    old = db.scalar(select(StockSupplier).where(StockSupplier.institute_id == institute,
        StockSupplier.idempotency_key == payload.idempotency_key))
    if old:
        if (old.reference, old.name, old.reason, old.actor_id) != (payload.reference, payload.name, payload.reason, actor):
            raise business_error("La cle fournisseur conserve les conditions originales")
        return snapshot(old)
    if db.scalar(select(StockSupplier.id).where(StockSupplier.institute_id == institute,
        StockSupplier.reference == payload.reference)):
        raise business_error("Cette reference fournisseur existe deja dans cet institut")
    row = StockSupplier(id=new_id(), institute_id=institute, reference=payload.reference,
        name=payload.name, reason=payload.reason, actor_id=actor,
        idempotency_key=payload.idempotency_key, created_at=utcnow())
    db.add(row)
    db.commit()
    db.refresh(row)
    return snapshot(row)


def list_suppliers(db, institute, limit, offset):
    rows = db.scalars(select(StockSupplier).where(StockSupplier.institute_id == institute)
        .order_by(StockSupplier.reference, StockSupplier.id).limit(limit).offset(offset))
    return [snapshot(row) for row in rows]
