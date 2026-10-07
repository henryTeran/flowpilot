from datetime import timedelta
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.marketing import conversion_catalogs as service, conversion_originals
from app.modules.marketing.models import ConversionOriginal, ConversionHead
from app.modules.tickets.models import QueueTicket
from test_marketing_conversion_originals_13az import setup
from test_crm_billing_12b import NOW
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers


def exercise(engine, institute, monkeypatch):
    base = setup(engine, institute, monkeypatch)
    monkeypatch.setattr(service, "utcnow", lambda: NOW + timedelta(days=4))
    window = service.Request(start=NOW + timedelta(microseconds=5), end=NOW + timedelta(days=2))
    campaign = None; linked = []
    with Session(engine) as db:
        for index in range(27):
            ticket = f"report-ticket-{index:02}"
            db.add(QueueTicket(id=ticket, institute_id=institute, customer_id="aud_000", ticket_number=ticket, status="paid", arrival_time=NOW,
                paid_at=NOW + timedelta(days=1), currency="EUR" if index == 2 else None if index == 3 else "CHF",
                total_amount=None if index == 0 else Decimal("-1") if index == 1 else Decimal("1.01"))); db.commit()
            selection = base.selection.model_copy(update={"ticket_id": ticket, "idempotency_key": ticket})
            request = base.model_copy(update={"ticket_id": ticket, "selection": selection, "idempotency_key": ticket})
            original = conversion_originals.execute(db, institute, request, "manager")
            linked.append(original); campaign = original.attribution.intent.request.campaign_id
        # Explicitly retract two; the 25 remaining links exceed one native page.
        for original in linked[-2:]:
            conversion_originals.execute(db, institute, conversion_originals.Request(action="retracted", ticket_id=original.request.ticket_id,
                expected_previous_id=original.id, selection=None, reason="Explicit exclusion", idempotency_key="retract-" + original.id), "manager")
        count = db.scalar(select(func.count()).select_from(ConversionOriginal))
        report = service.report(db, institute, campaign, window)
        assert report.selected_current_links == report.summary.linked_tickets == report.summary.test_linked_tickets == 25
        assert report.summary.live_linked_tickets == 0 and report.summary.unknown_currency_test_tickets == 1
        chf, eur = report.summary.currencies
        assert chf.currency == "CHF" and chf.known_gross_minor == "2121" and chf.missing_amount_tickets == chf.invalid_amount_tickets == 1
        assert eur.currency == "EUR" and eur.known_gross_minor == "101"
        assert report.full_retained_current_cohort and not report.summary.complete_campaign_history and not report.summary.causal_effect_proven
        assert report.summary.conversion_rate is report.summary.return_on_ad_spend is None
        first = service.current_links(db, institute, campaign, window)
        last = service.current_links(db, institute, campaign, window, 20)
        assert first.total == last.total == 25 and len(first.items) == 20 and len(last.items) == 5
        assert [o.request.ticket_id for o in first.items + last.items] == sorted(o.request.ticket_id for o in linked[:-2])
        assert service.current_links(db, institute, campaign, window, 25).items == ()
        outside = service.Request(start=NOW + timedelta(days=2), end=NOW + timedelta(days=3))
        assert service.report(db, institute, campaign, outside).selected_current_links == 0
        assert db.scalar(select(func.count()).select_from(ConversionOriginal)) == count
        assert service.report(db, institute, campaign, window) == report
        # An explicit correction replaces the current amount without counting
        # its retained predecessor twice; changing billing alone changes nothing.
        original = linked[4]
        ticket = db.get(QueueTicket, original.request.ticket_id)
        ticket.total_amount = Decimal("2.02"); db.commit()
        assert service.report(db, institute, campaign, window) == report
        selection = original.request.selection.model_copy(update={"idempotency_key": "correct-report"})
        corrected = conversion_originals.execute(db, institute, original.request.model_copy(update={
            "expected_previous_id": original.id, "selection": selection, "idempotency_key": "correct-report"}), "manager")
        corrected_report = service.report(db, institute, campaign, window)
        assert corrected_report.selected_current_links == 25
        assert corrected_report.summary.currencies[0].known_gross_minor == "2222"
        assert conversion_originals.original(db, institute, original.request.idempotency_key) == original
        assert corrected.id != original.id
        monkeypatch.setattr(service, "utcnow", lambda: NOW + timedelta(days=2))
        with pytest.raises(HTTPException): service.report(db, institute, campaign, window)
        monkeypatch.setattr(service, "utcnow", lambda: NOW + timedelta(days=4))
        # Corruption beyond the first page must hide even that first page/report.
        row = db.get(ConversionOriginal, linked[24].id); saved = row.attribution_fingerprint
        row.attribution_fingerprint = "0" * 64; db.commit()
        with pytest.raises(HTTPException): service.current_links(db, institute, campaign, window)
        with pytest.raises(HTTPException): service.report(db, institute, campaign, outside)
        row.attribution_fingerprint = saved; db.commit()
        pointer = db.get(ConversionHead, (institute, linked[24].request.ticket_id)); db.delete(pointer); db.commit()
        with pytest.raises(HTTPException): service.report(db, institute, campaign, window)
        db.add(ConversionHead(institute_id=institute, ticket_id=linked[24].request.ticket_id, original_id=linked[24].id)); db.commit()
        with pytest.raises(HTTPException): service.report(db, "foreign", campaign, window)
        with pytest.raises(HTTPException): service.report(db, institute, campaign, service.Request(start=window.start, end=NOW + timedelta(days=5)))
        for offset, limit in [(-1,20), (0,51), (True,20)]:
            with pytest.raises(HTTPException): service.current_links(db, institute, campaign, window, offset, limit)
        assert service.report(db, institute, campaign, window) == corrected_report
    return campaign, window


def test_sqlite_full_current_conversion_cohort_and_signed_manager_scope(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client); campaign, window = exercise(main_module.engine, institute, monkeypatch)
    base = f"/api/v1/marketing/institutes/{institute}/campaigns/{campaign}/conversions"
    params = window.model_dump(mode="json"); headers = _auth_headers("responsable_institut", institute)
    assert client.get(base + "/summary", headers=headers, params=params).json()["selected_current_links"] == 25
    assert client.get(base + "/current", headers=headers, params=params).json()["total"] == 25
    for suffix in ("/summary", "/current"):
        for role, owner in [("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")]:
            assert client.get(base + suffix, headers=_auth_headers(role, owner), params=params).status_code == 403
        assert client.get(base + suffix, params=params).status_code == 403
        assert client.get(base + suffix, headers=headers, params={**params, "start": "2026-10-07"}).status_code == 422


def test_postgres_full_current_conversion_cohort(postgres_flow, monkeypatch):
    exercise(postgres_flow[0], postgres_flow[1], monkeypatch)
