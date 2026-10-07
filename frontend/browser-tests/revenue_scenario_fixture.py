"""Known paid source only in the harness-owned disposable database."""
import os
import sys
from pathlib import Path
from tempfile import gettempdir
from datetime import datetime, timezone
from decimal import Decimal

directory = Path(os.environ["FLOWPILOT_BROWSER_DIRECTORY"]).resolve()
if (directory.parent != Path(gettempdir()).resolve() or not directory.name.startswith("flowpilot-browser-")
        or not (directory / ".flowpilot-browser-owner").is_file() or not (directory / "browser.sqlite").is_file()):
    raise RuntimeError("Existing owned browser fixture required")
suffix = sys.argv[1]
if suffix not in ("desktop", "tablet-landscape"):
    raise RuntimeError("Known browser project required")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
os.environ.update(DATABASE_URL="sqlite:///" + (directory / "browser.sqlite").as_posix(),
    APP_ENV="test", SECRET_KEY="isolated-revenue-fixture-only", AUTO_CREATE_SCHEMA_ON_STARTUP="false")
from app.main import app  # Register complete topology; no application startup/migration.
from app.database.session import engine
from sqlalchemy.orm import Session
from app.modules.tickets.models import QueueTicket

with Session(engine) as db:
    clock = datetime(2026, 1, 2, 12, tzinfo=timezone.utc)
    identifier = "scenario-source-" + suffix
    db.add(QueueTicket(id=identifier, institute_id="demo-institute-geneve", ticket_number=identifier,
        status="paid", arrival_time=clock, paid_at=clock, currency="CHF", total_amount=Decimal("1.01")))
    db.commit()
engine.dispose()
