"""Historical commercial fixtures restricted to the runner-owned disposable DB."""
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
    raise RuntimeError("Known browser profile required")
os.environ.update(DATABASE_URL="sqlite:///"+(directory / "browser.sqlite").as_posix(), APP_ENV="test",
    SECRET_KEY="isolated-cancellation-fixture-only", AUTO_CREATE_SCHEMA_ON_STARTUP="false")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.main import app
from app.database.session import engine
from sqlalchemy import select
from sqlalchemy.orm import Session
from pytest import MonkeyPatch
from app.modules.tickets import service, events
from app.modules.tickets.models import QueueTicket, TicketLine, QueueEvent
from app.modules.services.models import Service

institute = "demo-institute-geneve"
base = datetime(2026, 1, 2 if suffix == "desktop" else 3, 12, tzinfo=timezone.utc)
with Session(engine) as db, MonkeyPatch.context() as patch:
    service_id = db.scalar(select(Service.id))
    ids = []
    for n in range(25):
        identifier = f"cancel-native-{suffix}-{n:02}"
        ids.append(identifier)
        db.add(QueueTicket(id=identifier, institute_id=institute, ticket_number=identifier, status="waiting", arrival_time=base,
            currency=None if n == 3 else "EUR" if n == 4 else "CHF",
            total_amount=Decimal("0") if n == 0 else None if n == 1 else Decimal("-1") if n == 2 else Decimal("1.01")))
    db.flush()
    for identifier in ids:
        db.add(TicketLine(id=identifier+"-line", ticket_id=identifier, service_id=service_id, quantity=2, duration_minutes=20,
            unit_price=Decimal("0.50"), total=Decimal("1.01"), invoice_removed_at=base-timedelta(minutes=1),
            invoice_removed_by_actor="fixture-correction", invoice_removal_reason="not_performed"))
    db.commit()
    for n, identifier in enumerate(ids):
        at = base+timedelta(seconds=n)
        patch.setattr(service, "utcnow", lambda: at)
        patch.setattr(events, "utcnow", lambda: at)
        service.cancel_ticket(db, identifier, "fixture-source 😀")
    legacy = f"cancel-native-{suffix}-legacy"
    db.add(QueueTicket(id=legacy, institute_id=institute, ticket_number=legacy, status="cancelled", arrival_time=base))
    db.flush()
    db.add(QueueEvent(institute_id=institute, ticket_id=legacy, event_type="queue.cancelled", previous_status="waiting",
        status="cancelled", occurred_at=base+timedelta(seconds=25)))
    # Current mutable prices cannot revalue the previously captured originals.
    for identifier in ids:
        db.get(QueueTicket, identifier).total_amount = Decimal("999")
        db.get(TicketLine, identifier+"-line").total = Decimal("999")
    db.commit()
print(json.dumps(dict(start="2026-01-01", end="2026-01-05", zero=ids[0], unknown=ids[3], legacy=legacy)))
engine.dispose()
