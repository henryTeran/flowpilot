"""Signed measured usage by actual completion time, with honest sample coverage."""
from sqlalchemy import select, literal, union_all, and_, or_
from app.modules.inventory.models import StockServiceBasis as Basis, StockConsumption, StockMovement, StockItem
from app.modules.planning.models import ServiceSession
from app.modules.appointments.models import Appointment
from app.modules.inventory import service as stock, outlook
from app.modules.inventory.projection import ProjectionWindow
from app.modules.inventory.observed_schemas import ObservedRead, ObservedItem
from app.shared.time import utcnow
from app.shared.exceptions import business_error


def sources(institute, window):
    parts = []
    for model, basis_field, kind, end in (
        (ServiceSession, Basis.session_id, "sessions", ServiceSession.real_end_time),
        (Appointment, Basis.appointment_id, "appointments", Appointment.actual_end_time)):
        parts.append(select(literal(kind).label("source_kind"), model.id.label("source_id"),
            end.label("completed_at"), Basis.id.label("basis_id"),
            StockConsumption.id.label("consumption_id")).select_from(model).outerjoin(Basis,
                and_(basis_field == model.id, Basis.institute_id == model.institute_id)).outerjoin(
                StockConsumption, and_(StockConsumption.basis_id == Basis.id,
                    StockConsumption.institute_id == model.institute_id,
                    StockConsumption.created_at <= window.generated_at)).where(
                model.institute_id == institute, model.status == "completed",
                or_(end.is_(None), and_(end >= window.observed_start, end < window.observed_end))))
    return union_all(*parts).subquery()


def read(db, institute, payload, limit, offset):
    stock.lock_institute(db, institute)
    try:
        window = ProjectionWindow.create(payload.starts_at, payload.ends_at,
            payload.observed_starts_at, payload.observed_ends_at, utcnow())
    except ValueError as error:
        raise business_error("Periodes a verifier : historique termine et horizon futur non expire requis") from error
    source = sources(institute, window)
    counts = dict(completed_executions=0, captured_bases=0, signed_confirmations=0,
        pending_bases=0, legacy_completed_executions=0, undated_completed_executions=0)
    previous = None
    for row in db.execute(select(source).order_by(source.c.source_kind, source.c.source_id,
            source.c.basis_id)).mappings().yield_per(200):
        key = (row["source_kind"], row["source_id"])
        first = key != previous
        previous = key
        if row["completed_at"] is None:
            counts["undated_completed_executions"] += int(first)
            continue
        counts["completed_executions"] += int(first)
        if row["basis_id"] is None:
            counts["legacy_completed_executions"] += int(first)
        else:
            counts["captured_bases"] += 1
            counts["signed_confirmations" if row["consumption_id"] else "pending_bases"] += 1
    complete = (counts["completed_executions"] > 0 and not any(counts[name] for name in
        ("pending_bases", "legacy_completed_executions", "undated_completed_executions")))
    coverage = "no_completed_sample" if not counts["completed_executions"] else (
        "complete_signed_sample" if complete else "partial_signed_sample")
    page = select(StockItem.id).where(StockItem.institute_id == institute).order_by(
        StockItem.sku, StockItem.id).limit(limit).offset(offset)
    query = select(StockMovement.item_id, StockMovement.quantity_milli, StockItem.unit).join(
        source, source.c.consumption_id == StockMovement.consumption_id).join(StockItem,
        and_(StockItem.id == StockMovement.item_id, StockItem.institute_id == StockMovement.institute_id)
    ).where(StockMovement.institute_id == institute, StockMovement.kind == "consumption",
        source.c.completed_at.is_not(None), StockMovement.item_id.in_(page))
    measured, units = {}, {}
    for item_id, signed_milli, unit in db.execute(query).yield_per(200):
        measured[item_id] = measured.get(item_id, 0) - signed_milli
        units[item_id] = unit
    try:
        projected = {item_id: window.project(amount, units[item_id]) for item_id, amount in measured.items()}
    except ValueError as error:
        raise business_error("Quantites observees a verifier") from error
    items = []
    for row in outlook.item_rows(db, institute, limit, offset, projected, complete):
        physical = {name: getattr(row, name) for name in ("item_id", "item_sku", "item_name",
            "category", "unit", "on_hand", "threshold", "at_or_below_threshold",
            "threshold_shortfall", "pending_order_quantity", "conditional_shortfall_after_all_orders")}
        items.append(ObservedItem(**physical, observed_quantity=outlook.quantity(measured.get(row.item_id, 0)),
            recorded_pace_projection=row.known_demand, complete_pace_projection=row.complete_demand,
            recorded_projection_shortfall=row.known_demand_shortfall))
    return ObservedRead(institute_id=institute, generated_at=window.generated_at,
        starts_at=window.requested_start, effective_starts_at=window.effective_start, ends_at=window.end,
        observed_starts_at=window.observed_start, observed_ends_at=window.observed_end,
        coverage=coverage, **counts, limit=limit, offset=offset, items=items)
