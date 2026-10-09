"""Explicit historical records in the owned, newly-created browser database only.

These are legacy observed payment snapshots, not simulated external payments or
claims about a complete checkout ledger. No application clock is overridden.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from app.modules.customers.models import Customer
from app.modules.tickets.models import QueueTicket


def seed_history(engine, institute):
    now = datetime.now(timezone.utc)
    manifest = []
    with Session(engine) as db:
        for project in ("desktop", "tablet-landscape"):
            for label, age in (("risk", 75), ("dormant", 120), ("outside", 400), ("absent", None)):
                identity = f"customer_browser_history_{project}_{label}"
                name = f"CRM history {project} {label}"
                db.add(Customer(id=identity, institute_id=institute, display_name=name,
                    phone="+33999111222", search_name=name.lower(), phone_digits="33999111222",
                    idempotency_key=identity, creation_fingerprint="0"*64,
                    created_at=now-timedelta(days=500), created_by="browser-history-fixture"))
                closed = now-timedelta(days=age) if age else None
                ticket_ids = []
                if closed:
                    for index in range(3):
                        ticket_id = f"history_{project}_{label}_{index}"
                        ticket_ids.append(ticket_id)
                        db.add(QueueTicket(id=ticket_id, institute_id=institute, customer_id=identity,
                            ticket_number=ticket_id, status="paid", arrival_time=closed-timedelta(hours=1),
                            paid_at=closed, currency="CHF", total_amount=Decimal("15.00"),
                            payment_method="especes", paid_employee_id="emp-angela"))
                manifest.append(dict(project=project, label=label, customer_id=identity,
                    name=name, paid_at=closed.isoformat() if closed else None, ticket_ids=ticket_ids))
        db.commit()
    return manifest
