"""Historical facts only in the runner-owned disposable browser database."""
import json
import os
from pathlib import Path
import sys
from tempfile import gettempdir
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

directory = Path(os.environ["FLOWPILOT_BROWSER_DIRECTORY"]).resolve()
if (directory.parent != Path(gettempdir()).resolve() or not directory.name.startswith("flowpilot-browser-")
        or not (directory / ".flowpilot-browser-owner").is_file() or not (directory / "browser.sqlite").is_file()):
    raise RuntimeError("Existing owned browser fixture required")
suffix = sys.argv[1]
if suffix not in ("desktop", "tablet-landscape"):
    raise RuntimeError("Known browser project required")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
os.environ.update(DATABASE_URL="sqlite:///" + (directory / "browser.sqlite").as_posix(),
    APP_ENV="test", SECRET_KEY="isolated-source-fixture-only", AUTO_CREATE_SCHEMA_ON_STARTUP="false")
from app.main import app  # Register the complete existing model topology.
from app.database.session import engine
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.modules.services.models import Service
from app.modules.inventory import service as stock, recipes, consumptions, bases
from app.modules.inventory.schemas import ItemCreate, MovementCreate, RecipeCreate, ConsumptionCreate
from app.modules.inventory.models import StockRecipe, StockServiceBasis, StockItem, StockMovement
from app.modules.planning.models import ServiceSession
from app.modules.appointments.models import Appointment
from app.modules.tickets.models import QueueTicket, TicketLine

now = datetime.now(timezone.utc)
civil = now.astimezone(ZoneInfo("Europe/Zurich")).date()
midnight = datetime.combine(civil, datetime.min.time(), ZoneInfo("Europe/Zurich")).astimezone(timezone.utc)
ended = midnight - timedelta(hours=12)
institute = "demo-institute-geneve"
service_id = "browser-source-" + suffix
with Session(engine) as db:
    original = db.scalar(select(Service))
    db.add(Service(id=service_id, category_id=original.category_id, name="Source " + suffix,
        duration_min=15, price_member=10, price_passage=10, status="active"))
    db.commit()
    item = stock.create_item(db, institute, ItemCreate(sku="SOURCE-" + suffix, name="Serum source " + suffix,
        category="cabine", unit="ml", reorder_threshold="4.125", reason="Owned historical fixture",
        idempotency_key="source-item-" + suffix), "browser-manager")
    receipt = stock.move(db, institute, item.id, MovementCreate(kind="receipt", quantity="10.125",
        reason="Historical fixture receipt", idempotency_key="source-receipt-" + suffix), "browser-manager")
    norm = recipes.create(db, institute, service_id, RecipeCreate(base_revision=0, enabled=True,
        entries=[dict(item_id=item.id, quantity="4.125")], reason="Historical fixture norm",
        idempotency_key="source-norm-" + suffix), "browser-manager")
    db.get(StockRecipe, norm.id).created_at = ended-timedelta(days=1)
    db.get(StockItem, item.id).created_at = ended-timedelta(days=2)
    db.get(StockMovement, receipt.id).occurred_at = ended-timedelta(days=1, hours=1)
    ticket_id, line_id, session_id = ("source-history-" + suffix + tail for tail in ("-ticket", "-line", "-session"))
    db.add(QueueTicket(id=ticket_id, institute_id=institute, ticket_number=ticket_id,
        status="ready_for_checkout", arrival_time=ended-timedelta(hours=1)))
    db.flush()
    db.add(TicketLine(id=line_id, ticket_id=ticket_id, service_id=service_id, quantity=1,
        duration_minutes=15, performed_by_employee_id="emp-angela"))
    db.flush()
    db.add(ServiceSession(id=session_id, institute_id=institute, employee_id="emp-angela",
        service_id=service_id, ticket_line_id=line_id, start_time=ended-timedelta(minutes=15),
        planned_end_time=ended, real_end_time=ended, duration_minutes=15, status="completed"))
    db.flush()
    stock.lock_institute(db, institute)
    bases.capture(db, institute, service_id, 1, ended-timedelta(minutes=15), "browser-manager",
        session_id=session_id, ticket_line_id=line_id)
    db.commit()
    basis = db.scalar(select(StockServiceBasis.id).where(StockServiceBasis.session_id == session_id))
    consumptions.create(db, institute, basis, ConsumptionCreate(entries=[dict(item_id=item.id, quantity="4.125")],
        reason="Late signed historical fixture measurement", idempotency_key="source-usage-" + suffix), "browser-manager")
    recipes.create(db, institute, service_id, RecipeCreate(base_revision=1, enabled=True,
        entries=[dict(item_id=item.id, quantity="8.250")], reason="Later provisional fixture norm",
        idempotency_key="source-new-norm-" + suffix), "browser-manager")
    future = datetime.combine(civil+timedelta(days=1), datetime.min.time(), ZoneInfo("Europe/Zurich")).astimezone(timezone.utc)+timedelta(hours=12)
    db.add(Appointment(id="source-upcoming-"+suffix, institute_id=institute, employee_id="emp-angela",
        service_id=service_id, customer_name="Private fixture name", start_time=future,
        end_time=future+timedelta(minutes=15), status="scheduled"))
    queue_id = "source-waiting-"+suffix
    db.add(QueueTicket(id=queue_id, institute_id=institute, ticket_number=queue_id, status="waiting", arrival_time=now))
    db.flush()
    db.add(TicketLine(id=queue_id+"-line", ticket_id=queue_id, service_id=service_id, quantity=2, duration_minutes=15))
    db.commit()
    future_start = datetime.combine(civil+timedelta(days=1), datetime.min.time(), ZoneInfo("Europe/Zurich")).astimezone(timezone.utc)
    future_end = datetime.combine(civil+timedelta(days=2), datetime.min.time(), ZoneInfo("Europe/Zurich")).astimezone(timezone.utc)
    observed_start = datetime.combine(civil-timedelta(days=7), datetime.min.time(), ZoneInfo("Europe/Zurich")).astimezone(timezone.utc)
    from app.modules.inventory.projection import ProjectionWindow
    projected = ProjectionWindow.create(future_start, future_end, observed_start, midnight, now).project(4125, "ml")
    print(json.dumps(dict(item_id=item.id, sku=item.sku, projected_quantity=f"{projected//1000}.{projected%1000:03d}",
        future_start=str(civil+timedelta(days=1)), future_end=str(civil+timedelta(days=2)),
        observed_start=str(civil-timedelta(days=7)), observed_end=str(civil))))
engine.dispose()
