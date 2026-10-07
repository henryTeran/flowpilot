"""Explicit owned browser fixture; actual services/fake adapter, no external I/O."""
import sys
from datetime import datetime, timezone
from pathlib import Path


def seed_conversion(engine, institute):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend/tests"))
    from pytest import MonkeyPatch
    from sqlalchemy.orm import Session
    from test_marketing_conversion_sources_13ax import exercise
    from app.modules.marketing import campaign_originals
    from app.modules.tickets.models import QueueTicket
    with MonkeyPatch.context() as patch:
        # Shared test source fixtures are deterministic; restore every app clock
        # and account configuration before the real browser server starts.
        for name, module in tuple(sys.modules.items()):
            if name.startswith("test_") and hasattr(module, "NOW"):
                patch.setattr(module, "NOW", datetime(2020, 1, 2, 12, tzinfo=timezone.utc))
        selection = exercise(engine, institute, patch)
        with Session(engine) as db:
            campaign = campaign_originals.require(db, institute, selection.authorization_id)
            paid = db.get(QueueTicket, selection.ticket_id)
            db.add(QueueTicket(id="browser-tablet-paid", institute_id=institute, customer_id=paid.customer_id,
                ticket_number="browser-tablet-paid", status="paid", arrival_time=paid.arrival_time,
                paid_at=paid.paid_at, currency=paid.currency, total_amount=paid.total_amount))
            db.commit()
    return dict(institute_id=institute, campaign_id=campaign.revision.campaign_id,
        label=(campaign.revision.content.subject or campaign.revision.content.body[:80]) + " · Envoi autorisé · email",
        intent_id=selection.intent_id, ticket_ids={"desktop": selection.ticket_id, "tablet-landscape": "browser-tablet-paid"},
        start_date="2020-01-02", end_date="2020-01-05")
