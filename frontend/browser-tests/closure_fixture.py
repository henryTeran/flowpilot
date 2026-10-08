"""Historical bookings only inside the runner-owned disposable browser database."""
import os
import sys
import json
from pathlib import Path
from tempfile import gettempdir
from datetime import datetime, timedelta, timezone
from decimal import Decimal

directory = Path(os.environ["FLOWPILOT_BROWSER_DIRECTORY"]).resolve()
if (directory.parent != Path(gettempdir()).resolve() or not directory.name.startswith("flowpilot-browser-")
        or not (directory / ".flowpilot-browser-owner").is_file() or not (directory / "browser.sqlite").is_file()):
    raise RuntimeError("Existing owned browser fixture required")
suffix = sys.argv[1]
if suffix not in ("desktop", "tablet-landscape"):
    raise RuntimeError("Known browser project required")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
os.environ.update(DATABASE_URL="sqlite:///" + (directory / "browser.sqlite").as_posix(), APP_ENV="test",
    SECRET_KEY="isolated-closure-fixture-only", AUTO_CREATE_SCHEMA_ON_STARTUP="false")
from app.main import app
from app.database.session import engine
from sqlalchemy import select
from sqlalchemy.orm import Session
from pytest import MonkeyPatch
from app.modules.appointments import service as bookings, events
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.appointments.schemas import AppointmentCreate, AppointmentUpdate
from app.modules.services.models import Service
from app.modules.gift_cards.models import GiftCardSettings
from app.modules.resources.models import EmployeeSkill

institute, employee = "demo-institute-geneve", "emp-angela"
base = datetime(2026, 1, 2 if suffix == "desktop" else 3, 12, tzinfo=timezone.utc)
with Session(engine) as db, MonkeyPatch.context() as patch:
    source = db.scalar(select(Service))
    service_a, service_b = "closure-a-"+suffix, "closure-b-"+suffix
    for identifier, member in ((service_a, "9.87"), (service_b, "11.11")):
        db.add(Service(id=identifier, category_id=source.category_id, name="Closure source "+suffix,
            duration_min=30, duration_max=30, price_member=Decimal(member), price_passage=Decimal("12.34"), status="active"))
    if db.get(EmployeeSkill, (employee, "closure-fixture")) is None:
        db.add(EmployeeSkill(institute_id=institute, employee_id=employee, skill_code="closure-fixture"))
    settings = db.get(GiftCardSettings, institute)
    if settings is None:
        settings = GiftCardSettings(institute_id=institute); db.add(settings)
    settings.currency = "CHF"; settings.updated_at = base; settings.actor_id = "fixture-configured"
    db.commit()
    first = None
    for n in range(25):
        clock = base+timedelta(minutes=n*2)
        patch.setattr(bookings, "utcnow", lambda: clock); patch.setattr(events, "utcnow", lambda: clock)
        appointment = bookings.create_appointment(db, AppointmentCreate(institute_id=institute, employee_id=employee,
            service_id=service_a, customer_name="Private closure fixture", start_time=base+timedelta(hours=3+n*2)), "fixture-source")
        if n == 0:
            first = appointment.id
            for k in range(1, 25):
                clock = base+timedelta(seconds=k)
                bookings.update_appointment(db, appointment.id, AppointmentUpdate(service_id=service_b if k % 2 else service_a), "fixture-source")
        clock += timedelta(seconds=1)
        (bookings.cancel_appointment if n % 2 == 0 else bookings.mark_appointment_no_show)(db, appointment.id, "fixture-source")
    db.add(Appointment(id="closure-legacy-"+suffix, institute_id=institute, employee_id=employee, service_id=service_a,
        customer_name="Private legacy fixture", start_time=base, end_time=base+timedelta(minutes=30), status="cancelled"))
    db.get(Service, service_a).price_member = Decimal("99")  # Never reprice the retained references.
    db.commit()
    print(json.dumps(dict(appointment_id=first, start="2026-01-01", end="2026-01-05")))
engine.dispose()
