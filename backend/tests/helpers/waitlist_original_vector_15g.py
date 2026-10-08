"""Pure DTO/JSON vector generation; no database connection or application import."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
from app.modules.waitlist.domain import Demand
from app.modules.waitlist.originals import Source, Original, Envelope, Audit, fingerprint

now = datetime(2026, 10, 8, 10, tzinfo=timezone.utc)
demand = Demand(institute_id="own", customer_id="customer", service_id="care", declared_at=now,
    duration_minutes=30, availability=[dict(start=now+timedelta(hours=1), end=now+timedelta(hours=2))],
    allowed_employee_ids=["employee"], constraints_review="confirmed", availability_evidence="Déclaration cliente 😀",
    constraints_evidence="Contraintes relues avec cliente")
original = Original(id="waitlist_demand_000", institute_id="own", actor_id="manager-É", created_at=now,
    idempotency_key="waitlist-vector", reason="Demande déclarée\navec preuve", demand=demand,
    source=Source(customer_id="customer", registered_at=now-timedelta(days=3), service_id="care",
        duration_minutes=30, allowed_employee_ids=["employee"]))
raw = original.model_dump(mode="json")
audit = Audit(institute_id="own", captured_at=now+timedelta(minutes=1), offset=0, limit=20, total=1,
    originals=(Envelope(original=raw, fingerprint=fingerprint(raw)),))
target = Path(__file__).resolve().parents[3]/"frontend/tests/fixtures/waitlist-originals-15g.json"
target.write_text(json.dumps(audit.model_dump(mode="json"), ensure_ascii=True, indent=2)+"\n", encoding="utf-8")
