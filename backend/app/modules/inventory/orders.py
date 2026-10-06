"""Immutable orders and atomic, measured partial purchase receipts."""
from decimal import Decimal
from sqlalchemy import select, func
from app.modules.inventory.models import StockPurchaseOrder as Order, StockPurchaseOrderLine as Line, StockPurchaseReceipt as Receipt, StockPurchaseReceiptLine as ReceiptLine, StockMovement
from app.modules.inventory.order_schemas import OrderRead, OrderEntryRead, ReceiptRead, ReceiptEntryRead, OrderProgressRead, ProgressEntryRead
from app.modules.inventory import service as stock, suppliers
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


def require_order(db, institute, identifier):
    row = db.scalar(select(Order).where(Order.id == identifier, Order.institute_id == institute))
    if row is None:
        raise not_found("Commande introuvable")
    return row


def lines(db, institute, identifier):
    return db.scalars(select(Line).where(Line.institute_id == institute, Line.order_id == identifier).order_by(Line.item_id)).all()


def entry(row):
    return OrderEntryRead(item_id=row.item_id, item_name=row.item_name, item_sku=row.item_sku, unit=row.unit, quantity=Decimal(row.quantity_milli) / 1000)


def snapshot(db, row, entries=None):
    return OrderRead(id=row.id, institute_id=row.institute_id, supplier_id=row.supplier_id,
        supplier_reference=row.supplier_reference, supplier_name=row.supplier_name, reference=row.reference,
        reason=row.reason, actor_id=row.actor_id, idempotency_key=row.idempotency_key, created_at=row.created_at,
        entries=[entry(line) for line in (entries if entries is not None else lines(db, row.institute_id, row.id))])


def terms(entries):
    return sorted((row.item_id, row.unit, stock.milli(row.quantity, row.unit)) for row in entries)


def create(db, institute, payload, actor):
    stock.lock_institute(db, institute)
    requested = terms(payload.entries)
    old = db.scalar(select(Order).where(Order.institute_id == institute, Order.idempotency_key == payload.idempotency_key))
    if old:
        if (old.supplier_id, old.reference, old.reason, old.actor_id) != (payload.supplier_id, payload.reference, payload.reason, actor) or sorted((row.item_id, row.unit, row.quantity_milli) for row in lines(db, institute, old.id)) != requested:
            raise business_error("La cle commande conserve les conditions originales")
        return snapshot(db, old)
    supplier = suppliers.require_supplier(db, institute, payload.supplier_id)
    if db.scalar(select(Order.id).where(Order.institute_id == institute, Order.reference == payload.reference)):
        raise business_error("Cette reference commande existe deja")
    planned = []
    for item_id, unit, quantity in requested:
        item = stock.require_item(db, institute, item_id)
        if item.unit != unit:
            raise business_error("L'unite commandee doit correspondre a l'article")
        planned.append((item, unit, quantity))
    row = Order(id=new_id(), institute_id=institute, supplier_id=supplier.id,
        supplier_reference=supplier.reference, supplier_name=supplier.name, reference=payload.reference,
        reason=payload.reason, actor_id=actor, idempotency_key=payload.idempotency_key, created_at=utcnow())
    db.add(row)
    db.flush()
    for item, unit, quantity in planned:
        db.add(Line(order_id=row.id, institute_id=institute, item_id=item.id, item_name=item.name,
            item_sku=item.sku, unit=unit, quantity_milli=quantity))
    db.commit()
    return snapshot(db, row)


def list_orders(db, institute, limit, offset):
    rows = db.scalars(select(Order).where(Order.institute_id == institute).order_by(Order.created_at.desc(), Order.id).limit(limit).offset(offset)).all()
    grouped = {row.id: [] for row in rows}
    if rows:
        for line in db.scalars(select(Line).where(Line.institute_id == institute, Line.order_id.in_(grouped)).order_by(Line.item_id)):
            grouped[line.order_id].append(line)
    return [snapshot(db, row, grouped[row.id]) for row in rows]


def received(db, institute, order_id):
    return dict(db.execute(select(ReceiptLine.item_id, func.sum(ReceiptLine.quantity_milli)).where(
        ReceiptLine.institute_id == institute, ReceiptLine.order_id == order_id).group_by(ReceiptLine.item_id)).all())


def progress(db, institute, order_id):
    stock.lock_institute(db, institute)
    require_order(db, institute, order_id)
    totals = received(db, institute, order_id)
    entries = [ProgressEntryRead(**entry(row).model_dump(), received=Decimal(totals.get(row.item_id, 0)) / 1000,
        remaining=Decimal(row.quantity_milli - totals.get(row.item_id, 0)) / 1000) for row in lines(db, institute, order_id)]
    state = "received" if all(row.remaining == 0 for row in entries) else "partial" if any(row.received > 0 for row in entries) else "pending"
    return OrderProgressRead(institute_id=institute, order_id=order_id, state=state, entries=entries)


def receipt_snapshot(db, row, entries=None):
    if entries is None:
        entries = db.scalars(select(ReceiptLine).where(ReceiptLine.institute_id == row.institute_id, ReceiptLine.receipt_id == row.id).order_by(ReceiptLine.item_id))
    return ReceiptRead(id=row.id, institute_id=row.institute_id, order_id=row.order_id, reason=row.reason,
        actor_id=row.actor_id, idempotency_key=row.idempotency_key, occurred_at=row.occurred_at,
        entries=[ReceiptEntryRead(item_id=line.item_id, unit=line.unit, quantity=Decimal(line.quantity_milli) / 1000, movement_id=line.movement_id) for line in entries])


def list_receipts(db, institute, order_id, limit, offset):
    require_order(db, institute, order_id)
    rows = db.scalars(select(Receipt).where(Receipt.institute_id == institute, Receipt.order_id == order_id)
        .order_by(Receipt.occurred_at, Receipt.id).limit(limit).offset(offset)).all()
    grouped = {row.id: [] for row in rows}
    if rows:
        for line in db.scalars(select(ReceiptLine).where(ReceiptLine.institute_id == institute,
                ReceiptLine.receipt_id.in_(grouped)).order_by(ReceiptLine.item_id)):
            grouped[line.receipt_id].append(line)
    return [receipt_snapshot(db, row, grouped[row.id]) for row in rows]


def require_receipt(db, institute, identifier):
    row = db.scalar(select(Receipt).where(Receipt.institute_id == institute, Receipt.id == identifier))
    if row is None:
        raise not_found("Reception introuvable")
    return row


def receive(db, institute, order_id, payload, actor):
    stock.lock_institute(db, institute)
    requested = terms(payload.entries)
    old = db.scalar(select(Receipt).where(Receipt.institute_id == institute, Receipt.idempotency_key == payload.idempotency_key))
    if old:
        original = receipt_snapshot(db, old)
        if (old.order_id, old.reason, old.actor_id) != (order_id, payload.reason, actor) or terms(original.entries) != requested:
            raise business_error("La cle reception conserve les conditions originales")
        return original
    require_order(db, institute, order_id)
    ordered = {line.item_id: line for line in lines(db, institute, order_id)}
    totals = received(db, institute, order_id)
    for item_id, unit, quantity in requested:
        line = ordered.get(item_id)
        if line is None or line.unit != unit:
            raise business_error("Article et unite de la commande requis")
        item = stock.require_item(db, institute, item_id)
        if item.unit != unit or int(totals.get(item_id, 0)) + quantity > line.quantity_milli:
            raise business_error("La reception depasse la quantite commandee ou change l'unite")
        if stock.balance_milli(db, institute, item_id) + quantity > stock.MAX_MILLI:
            raise business_error("La reception depasse la capacite de stock")
    row = Receipt(id=new_id(), institute_id=institute, order_id=order_id, reason=payload.reason,
        actor_id=actor, idempotency_key=payload.idempotency_key, occurred_at=utcnow())
    db.add(row)
    db.flush()
    for index, (item_id, unit, quantity) in enumerate(requested):
        movement = StockMovement(id=new_id(), institute_id=institute, item_id=item_id, kind="receipt",
            quantity_milli=quantity, reason=payload.reason, actor_id=actor,
            idempotency_key=f"purchase:{row.id}:{index}", occurred_at=row.occurred_at)
        db.add(movement)
        db.flush()
        db.add(ReceiptLine(receipt_id=row.id, institute_id=institute, order_id=order_id, item_id=item_id,
            unit=unit, quantity_milli=quantity, movement_id=movement.id))
    db.commit()
    return receipt_snapshot(db, row)
