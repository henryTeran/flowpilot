"""Freeze recipe identity at actual start; never backfill historical execution."""
from sqlalchemy import select
from app.modules.inventory import recipes
from app.modules.inventory.models import StockServiceBasis, StockRecipe
from app.modules.planning.models import ServiceSession
from app.modules.appointments.models import Appointment
from app.shared.ids import new_id
from app.shared.exceptions import not_found, business_error


def capture(db, institute, service_id, quantity, timestamp, actor, **source):
    # Caller owns the institute lock and commits this with the execution start.
    if quantity < 1:
        raise business_error("Une prestation realisee exige une quantite positive")
    recipe = recipes.current(db, institute, service_id)
    db.add(StockServiceBasis(id=new_id(), institute_id=institute, service_id=service_id,
        quantity=quantity, recipe_id=recipe.id if recipe else None,
        state=("enabled" if recipe.enabled else "disabled") if recipe else "unconfigured",
        actor_id=actor, captured_at=timestamp, **source))


def read(db, institute, source_kind, source_id):
    model, field = (ServiceSession, StockServiceBasis.session_id) if source_kind == "sessions" else (Appointment, StockServiceBasis.appointment_id)
    source = db.scalar(select(model).where(model.id == source_id, model.institute_id == institute))
    if source is None:
        raise not_found("Execution introuvable")
    rows = db.scalars(select(StockServiceBasis).where(StockServiceBasis.institute_id == institute,
        field == source_id).order_by(StockServiceBasis.id)).all()
    # An empty result is legacy/uncaptured, NOT unconfigured or zero consumption.
    return {"institute_id": institute, "source_kind": source_kind, "source_id": source_id,
        "captured": bool(rows), "entries": [{"id": row.id, "ticket_line_id": row.ticket_line_id,
            "service_id": row.service_id, "quantity": row.quantity, "state": row.state,
            "actor_id": row.actor_id, "captured_at": row.captured_at,
            "recipe": recipes.snapshot(db, db.get(StockRecipe, row.recipe_id)) if row.recipe_id else None}
            for row in rows]}
