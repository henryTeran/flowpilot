from datetime import timedelta, timezone
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.marketing import conversion_tickets as service
from app.modules.marketing import dispatch_outcomes
from app.modules.tickets.models import QueueTicket
from test_marketing_conversion_originals_13az import setup
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow
from test_crm_billing_12b import NOW


def exercise(engine, institute, monkeypatch):
    selection = setup(engine, institute, monkeypatch).selection
    monkeypatch.setattr(service, "utcnow", lambda: NOW + timedelta(days=4))
    payload = service.Request(intent_id=selection.intent_id, expected_fingerprint=selection.expected_fingerprint,
        accepted_outcome_id=selection.accepted_outcome_id, start=NOW + timedelta(hours=1), end=NOW + timedelta(days=2))
    with Session(engine) as db:
        # The setup's four owned paid tickets are also valid candidates.
        for n in range(25):
            db.add(QueueTicket(id=f"select-paid-{n:02}", institute_id=institute, customer_id="aud_000", ticket_number=f"select-{n}",
                arrival_time=NOW, status="paid", paid_at=NOW + timedelta(days=1), currency=None if n == 2 else "CHF",
                total_amount=None if n == 0 else Decimal("-1") if n == 1 else Decimal("1.01")))
        for suffix, status, paid in [("unpaid", "waiting", NOW), ("undated", "paid", None), ("end", "paid", payload.end)]:
            db.add(QueueTicket(id="exclude-" + suffix, institute_id=institute, customer_id="aud_000", ticket_number=suffix,
                arrival_time=NOW, status=status, paid_at=paid, currency="CHF", total_amount=Decimal("1.01")))
        db.commit()
        first = service.read(db, institute, payload); last = service.read(db, institute, payload, 20)
        assert first.page.total == last.page.total == 29
        assert len(first.page.items) == 20 and len(last.page.items) == 9
        facts = first.page.items + last.page.items
        assert len({f.ticket_id for f in facts}) == 29
        assert all(f.captured_at == first.window.captured_at and f.customer_id == "aud_000" for f in facts)
        amounts = {f.ticket_id: f for f in facts}
        assert amounts["select-paid-00"].amount_quality == "missing"
        assert amounts["select-paid-01"].amount_quality == "invalid"
        assert amounts["select-paid-02"].currency is None
        assert amounts["select-paid-03"].amount_minor == "101"
        alternate = payload.model_copy(update={"start": payload.start.astimezone(timezone(timedelta(hours=2))),
            "end": payload.end.astimezone(timezone(timedelta(hours=2)))})
        assert service.read(db, institute, alternate).page == first.page
        assert service.read(db, institute, payload, 29).page.items == ()
        for patch in [{"expected_fingerprint": "0"*64}, {"start": NOW - timedelta(days=1)}, {"end": NOW + timedelta(days=5)}]:
            with pytest.raises(HTTPException): service.read(db, institute, payload.model_copy(update=patch))
        unknown = next(o for o in dispatch_outcomes.audit(db, institute, payload.intent_id).items if o.request.result.status == "unknown")
        with pytest.raises(HTTPException): service.read(db, institute, payload.model_copy(update={"accepted_outcome_id": unknown.id}))
        with pytest.raises(HTTPException): service.read(db, "foreign", payload)
        for offset, limit in [(-1,20),(0,51),(True,20)]:
            with pytest.raises(HTTPException): service.read(db, institute, payload, offset, limit)
    return payload


def test_sqlite_paid_ticket_catalog_and_signed_scope(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    payload = exercise(main_module.engine, institute, monkeypatch)
    path = f"/api/v1/marketing/institutes/{institute}/dispatch-intents/{payload.intent_id}/conversion-tickets"
    params = payload.model_dump(mode="json"); params.pop("intent_id")
    headers = _auth_headers("responsable_institut", institute)
    assert client.get(path, headers=headers, params=params).json()["page"]["total"] == 29
    for role, owner in [("accueil", institute),("collaboratrice",institute),("responsable_institut","foreign")]:
        assert client.get(path, headers=_auth_headers(role, owner), params=params).status_code == 403
    assert client.get(path, params=params).status_code == 403
    assert client.get(path, headers=headers, params={**params,"start":"2026-10-07"}).status_code == 422


def test_postgres_paid_ticket_catalog(postgres_flow, monkeypatch):
    exercise(postgres_flow[0], postgres_flow[1], monkeypatch)
