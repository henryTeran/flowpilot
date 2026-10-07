from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.marketing import conversion_sources as service, campaign_originals, dispatch_outcomes
from app.modules.marketing.models import DispatchIntent, DispatchOutcome
from app.modules.tickets.models import QueueTicket
from app.modules.tickets.repository import lock_institute
from test_marketing_dispatch_worker_13ak import configured
from test_crm_billing_12b import NOW
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers


def exercise(engine, institute, monkeypatch):
    intent, adapter, run = configured(engine, institute, monkeypatch)
    outcome = run().outcome
    monkeypatch.setattr(service, "utcnow", lambda: NOW + timedelta(days=3))
    with Session(engine) as db:
        send = campaign_originals.current(db, institute, intent.request.campaign_id)
        for identity, customer, status, paid, amount, currency in [
            ("linked-paid", "aud_000", "paid", NOW + timedelta(days=1), Decimal("123.45"), "CHF"),
            ("other-customer", "aud_054", "paid", NOW + timedelta(days=1), Decimal("123.45"), "CHF"),
            ("unpaid", "aud_000", "waiting", NOW + timedelta(days=1), Decimal("123.45"), "CHF"),
            ("undated", "aud_000", "paid", None, Decimal("123.45"), "CHF"),
            ("future-paid", "aud_000", "paid", NOW + timedelta(days=4), Decimal("123.45"), "CHF"),
            ("missing-amount", "aud_000", "paid", NOW + timedelta(days=1), None, "EUR"),
            ("invalid-amount", "aud_000", "paid", NOW + timedelta(days=1), Decimal("-1"), "EUR"),
            ("unknown-currency", "aud_000", "paid", NOW + timedelta(days=1), Decimal("1"), None)]:
            db.add(QueueTicket(id=identity, institute_id=institute, customer_id=customer, ticket_number=identity,
                status=status, arrival_time=NOW, paid_at=paid, total_amount=amount, currency=currency))
        db.commit()
        payload = service.Request(intent_id=intent.id, expected_fingerprint=intent.request_fingerprint,
            authorization_id=send.revision.id, accepted_outcome_id=outcome.id, ticket_id="linked-paid",
            start=outcome.request.result.observed_at, end=NOW + timedelta(days=2), reason="Explicit recorded attribution preview", idempotency_key="preview-key")
        before = (db.scalar(select(func.count()).select_from(DispatchIntent)), db.scalar(select(func.count()).select_from(DispatchOutcome)))
        preview = service.validate(db, institute, payload, "manager")
        assert preview.retained is False and preview.attribution.actor_id == "manager"
        assert preview.attribution.ticket.amount_minor == "12345" and preview.attribution.ticket.currency == "CHF"
        assert preview.attribution.ticket.captured_at == preview.attribution.window.captured_at == NOW + timedelta(days=3)
        assert preview.attribution.intent == intent and preview.attribution.accepted == outcome and preview.attribution.authorization == send
        assert service.validate(db, institute, payload, "manager") == preview
        for patch in ({"ticket_id": "other-customer"}, {"ticket_id": "absent"}, {"ticket_id": "unpaid"}, {"ticket_id": "undated"},
            {"ticket_id": "future-paid"}, {"expected_fingerprint": "0" * 64}, {"authorization_id": intent.request.expected_revision_id},
            {"accepted_outcome_id": "missing"}, {"end": NOW + timedelta(days=4)}, {"start": NOW}):
            with pytest.raises(HTTPException): service.validate(db, institute, payload.model_copy(update=patch), "manager")
        unknown = next(o for o in dispatch_outcomes.audit(db, institute, intent.id).items if o.request.result.status == "unknown")
        with pytest.raises(HTTPException): service.validate(db, institute, payload.model_copy(update={"accepted_outcome_id": unknown.id}), "manager")
        for identity, quality, currency in [("missing-amount", "missing", "EUR"), ("invalid-amount", "invalid", "EUR"), ("unknown-currency", "known", None)]:
            fact = service.validate(db, institute, payload.model_copy(update={"ticket_id": identity}), "manager").attribution.ticket
            assert fact.amount_quality == quality and fact.currency == currency
        assert before == (db.scalar(select(func.count()).select_from(DispatchIntent)), db.scalar(select(func.count()).select_from(DispatchOutcome)))
        assert db.get(QueueTicket, "linked-paid").status == "paid"
        assert adapter.submits == 1 and adapter.reconciles == 0
    return payload


def test_sqlite_authoritative_conversion_preview_and_signed_roles(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    payload = exercise(main_module.engine, institute, monkeypatch)
    path = f"/api/v1/marketing/institutes/{institute}/conversions/validate"
    headers = _auth_headers("responsable_institut", institute)
    response = client.post(path, headers=headers, json=payload.model_dump(mode="json"))
    assert response.status_code == 200
    assert response.json()["retained"] is False and response.json()["attribution"]["actor_id"] == "test-user"
    for role, owner in [("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")]:
        assert client.post(path, headers=_auth_headers(role, owner), json=payload.model_dump(mode="json")).status_code == 403
    assert client.post(path, json=payload.model_dump(mode="json")).status_code == 403
    for extra in ({"actor_id": "forged"}, {"ticket": {"amount_minor": "99999"}}, {"accepted": {"status": "accepted"}}):
        assert client.post(path, headers=headers, json=payload.model_dump(mode="json") | extra).status_code == 422


def test_postgres_authoritative_conversion_preview(postgres_flow, monkeypatch):
    exercise(postgres_flow[0], postgres_flow[1], monkeypatch)


def test_postgres_billing_correction_waits_for_one_locked_capture(postgres_flow, monkeypatch):
    engine, institute = postgres_flow[:2]; payload = exercise(engine, institute, monkeypatch)
    ready, release, writer_started = Event(), Event(), Event(); clocks = []
    def clock():
        clocks.append(NOW + timedelta(days=3)); ready.set()
        assert release.wait(10)
        return clocks[-1]
    monkeypatch.setattr(service, "utcnow", clock)
    def read():
        with Session(engine) as db: return service.validate(db, institute, payload, "manager")
    def correct():
        with Session(engine) as db:
            writer_started.set(); lock_institute(db, institute)
            ticket = db.get(QueueTicket, "linked-paid"); ticket.total_amount = Decimal("43.21"); db.commit()
    with ThreadPoolExecutor(max_workers=2) as pool:
        reader = pool.submit(read); assert ready.wait(10)
        writer = pool.submit(correct); assert writer_started.wait(10)
        try:
            with pytest.raises(TimeoutError): writer.result(timeout=0.15)
        finally: release.set()
        preview = reader.result(timeout=10); writer.result(timeout=10)
    assert len(clocks) == 1 and preview.attribution.ticket.amount_minor == "12345"
    with Session(engine) as db:
        revised = service.validate(db, institute, payload, "manager")
    assert revised.attribution.ticket.amount_minor == "4321" and revised.retained is False
    assert preview.attribution.ticket.amount_minor == "12345"  # Old immutable preview is not a fresh fact.
