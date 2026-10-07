from datetime import timedelta
from decimal import Decimal
import copy
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.revenue import walk_in_cancellations as reads
from app.modules.tickets import service, events, cancellation_terms
from app.modules.tickets.models import QueueTicket, TicketLine, QueueEvent
from test_revenue_billing_14a import NOW
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def exercise(engine, institute, service_id, monkeypatch):
    monkeypatch.setattr(events, "utcnow", lambda: NOW)
    monkeypatch.setattr(service, "utcnow", lambda: NOW)
    monkeypatch.setattr(reads, "utcnow", lambda: NOW+timedelta(seconds=1))
    with Session(engine) as db:
        for n in range(25):
            db.add(QueueTicket(id=f"cancel-value-{n:02}", institute_id=institute, ticket_number=f"C{n}", status="waiting", arrival_time=NOW,
                currency=None if n == 2 else "EUR" if n == 3 else "CHF",
                total_amount=None if n == 0 else Decimal("-1") if n == 1 else Decimal("1.01")))
        db.flush()
        for n in range(25):
            db.add(TicketLine(id=f"cancel-value-line-{n}", ticket_id=f"cancel-value-{n:02}", service_id=service_id,
                quantity=2, duration_minutes=20, unit_price=Decimal("0.50"), total=Decimal("1.01")))
        db.commit()
        for n in range(25): service.cancel_ticket(db, f"cancel-value-{n:02}", "signed-manager")
        db.add(QueueTicket(id="legacy-unpriced", institute_id=institute, ticket_number="legacy", status="cancelled", arrival_time=NOW))
        db.flush()
        db.add(QueueEvent(institute_id=institute, ticket_id="legacy-unpriced", event_type="queue.cancelled", previous_status="waiting", status="cancelled", occurred_at=NOW))
        db.commit()
        start, end = NOW-timedelta(seconds=1), NOW+timedelta(seconds=1)
        first = reads.read(db, institute, start, end)
        last = reads.read(db, institute, start, end, 20)
        assert first.page.total == last.page.total == 26 and len(first.opportunities) == 20 and len(last.opportunities) == 6
        assert first.retained_terms_count == 25 and first.legacy_unpriced_count == 1
        unknown, chf, eur = first.retained_amounts
        assert unknown.complete_gross_minor is None and unknown.known_gross_minor == "101"
        assert chf.known_gross_minor == "2121" and chf.missing_amount_count == chf.invalid_amount_count == 1
        assert chf.complete_gross_minor is None and eur.complete_gross_minor == "101"
        assert first.cancelled_revenue is None and not first.causal_loss_proven
        rows = first.opportunities+last.opportunities
        assert rows[-1].confidence == "legacy_cancellation_unpriced" and rows[-1].estimated_value is None
        assert rows[4].estimated_value.amount_minor == "101"  # qty2 does not multiply extended basket
        assert all(row.evidence.original is None or cancellation_terms.fingerprint(row.evidence.original.terms) == row.evidence.original.fingerprint for row in rows)
        with pytest.raises(ValueError): reads.Opportunity.model_validate({**rows[0].model_dump(), "action_executed": 0})
        for offset, limit in ((-1,20), (0,51), (True,20)):
            with pytest.raises(HTTPException): reads.read(db, institute, start, end, offset, limit)
        with pytest.raises(HTTPException): reads.read(db, institute, start, end+timedelta(seconds=1))
        ticket = db.get(QueueTicket, "cancel-value-24"); ticket.total_amount = Decimal("999"); db.commit()
        assert reads.read(db, institute, start, end).retained_amounts == first.retained_amounts
        assert reads.read(db, institute, start, NOW).page.total == 0
        event = db.scalar(select(QueueEvent).where(QueueEvent.ticket_id == "cancel-value-24"))
        valid = copy.deepcopy(event.cancellation_terms)
        broken = copy.deepcopy(valid); broken["terms"]["amount_minor"] = "99999"
        event.cancellation_terms = broken; db.commit()
        with pytest.raises(HTTPException): reads.read(db, institute, start, end, limit=1)
        # Even a recomputed hash cannot make malformed or foreign typed terms valid.
        for update in ({"ticket_id": "foreign"}, {"realized_revenue": 0}, {"amount_quality": "missing"}):
            broken = copy.deepcopy(valid); broken["terms"].update(update)
            broken["fingerprint"] = cancellation_terms.fingerprint(broken["terms"])
            event.cancellation_terms = broken; db.commit()
            with pytest.raises(HTTPException): reads.read(db, institute, start, end, limit=1)
        event.cancellation_terms = valid; db.commit()
        db.add(QueueEvent(institute_id=institute, ticket_id=event.ticket_id, event_type="queue.cancelled", previous_status="waiting",
            status="cancelled", occurred_at=NOW-timedelta(days=10)))
        db.commit()
        with pytest.raises(HTTPException): reads.read(db, institute, start, end)
        duplicate = db.scalar(select(QueueEvent).where(QueueEvent.ticket_id == event.ticket_id, QueueEvent.occurred_at < start))
        db.delete(duplicate); db.commit()
        return first


def test_sqlite_retained_value_and_signed_bounded_reader(client, monkeypatch):
    institute, _, service_id, _, _ = setup(client)
    result = exercise(main_module.engine, institute, service_id, monkeypatch)
    path = f"/api/v1/revenue/institutes/{institute}/walk-in-cancellations"
    params = dict(start=result.window.start.isoformat(), end=result.window.end.isoformat())
    headers = _auth_headers("responsable_institut", institute)
    response = client.get(path, headers=headers, params=params)
    assert response.status_code == 200 and response.json()["page"]["total"] == 26
    for row in response.json()["opportunities"]:
        original = row["evidence"]["original"]
        if original: assert cancellation_terms.fingerprint(original["terms"]) == original["fingerprint"]
    for role, owner in (("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")):
        assert client.get(path, headers=_auth_headers(role, owner), params=params).status_code == 403
    assert client.get(path, params=params).status_code == 403
    assert client.get(path, headers=headers, params={**params, "start": "2026-01-01"}).status_code == 422
    assert client.get(path, headers=headers, params={**params, "limit": 51}).status_code == 422
    assert client.post(path, headers=headers, json=params).status_code == 405


def test_postgres_retained_value_reader(postgres_flow, monkeypatch):
    engine, institute, _, service_id = postgres_flow
    exercise(engine, institute, service_id, monkeypatch)
