"""Read actual unstarted sources, never forecast unrecorded arrivals."""
from sqlalchemy import select, func
from app.modules.appointments.models import Appointment
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.inventory.models import StockItem, StockRecipe, StockRecipeLine
from app.modules.inventory import service as stock, outlook
from app.modules.inventory.planned_schemas import PlannedRead
from app.modules.inventory.projection import utc_instant
from app.shared.exceptions import business_error
from app.shared.time import utcnow


def read(db, institute, payload, limit, offset):
    stock.lock_institute(db, institute)
    generated = utc_instant(utcnow())
    effective = max(payload.starts_at, generated)
    if payload.ends_at <= effective:
        raise business_error("L'horizon des besoins est deja termine")
    quantities = {}
    appointments = waiting_lines = 0
    # Include a still-unstarted slot overlapping now; exclude the upper boundary.
    query = select(Appointment.service_id).where(Appointment.institute_id == institute,
        Appointment.status.in_(("scheduled", "confirmed", "arrived")),
        Appointment.actual_start_time.is_(None), Appointment.actual_end_time.is_(None),
        Appointment.end_time > effective, Appointment.start_time < payload.ends_at)
    for service_id, in db.execute(query).yield_per(200):
        quantities[service_id] = quantities.get(service_id, 0) + 1
        appointments += 1
    if payload.include_waiting_queue:
        query = select(TicketLine.service_id, TicketLine.quantity).join(
            QueueTicket, QueueTicket.id == TicketLine.ticket_id).where(
            QueueTicket.institute_id == institute, QueueTicket.status.in_(("waiting", "assigned")),
            TicketLine.invoice_removed_at.is_(None), TicketLine.performed_by_employee_id.is_(None))
        for service_id, quantity in db.execute(query).yield_per(200):
            if quantity < 1:
                raise business_error("Quantite de prestation en attente a verifier")
            quantities[service_id] = quantities.get(service_id, 0) + quantity
            waiting_lines += 1
    # Batch all institute norms without a parameter per service or an N+1 read.
    latest = select(StockRecipe.service_id, func.max(StockRecipe.revision).label("revision")).where(
        StockRecipe.institute_id == institute).group_by(StockRecipe.service_id).subquery()
    current = select(StockRecipe).join(latest,
        (latest.c.service_id == StockRecipe.service_id) & (latest.c.revision == StockRecipe.revision)
    ).where(StockRecipe.institute_id == institute)
    multipliers = {}
    configured = set()
    disabled = 0
    for recipe in db.scalars(current).yield_per(200):
        volume = quantities.get(recipe.service_id, 0)
        if volume:
            configured.add(recipe.service_id)
            if recipe.enabled:
                multipliers[recipe.id] = volume
            else:
                disabled += volume
    missing = sum(volume for service_id, volume in quantities.items() if service_id not in configured)
    # Only this catalogue page needs quantity arithmetic; coverage is global.
    page = select(StockItem.id).where(StockItem.institute_id == institute).order_by(
        StockItem.sku, StockItem.id).limit(limit).offset(offset)
    query = select(StockRecipeLine.recipe_id, StockRecipeLine.item_id, StockRecipeLine.quantity_milli).join(
        StockRecipe, (StockRecipe.id == StockRecipeLine.recipe_id) &
        (StockRecipe.institute_id == StockRecipeLine.institute_id)).join(latest,
        (latest.c.service_id == StockRecipe.service_id) & (latest.c.revision == StockRecipe.revision)
    ).where(StockRecipeLine.institute_id == institute, StockRecipe.enabled.is_(True),
        StockRecipeLine.item_id.in_(page))
    known = {}
    for recipe_id, item_id, milli in db.execute(query).yield_per(200):
        known[item_id] = known.get(item_id, 0) + milli * multipliers.get(recipe_id, 0)
    return PlannedRead(institute_id=institute, generated_at=generated,
        starts_at=payload.starts_at, effective_starts_at=effective, ends_at=payload.ends_at,
        include_waiting_queue=payload.include_waiting_queue,
        coverage="partial_recorded_norms" if missing else "complete_recorded_norms",
        appointment_count=appointments, waiting_line_count=waiting_lines,
        service_quantity=sum(quantities.values()), missing_norm_quantity=missing,
        disabled_norm_quantity=disabled, limit=limit, offset=offset,
        items=outlook.item_rows(db, institute, limit, offset, known, not missing))
