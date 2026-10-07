from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from decimal import Decimal, localcontext
from threading import Event

import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.crm import billing
from app.modules.customers.models import Customer
from app.modules.institutes.models import Institute
from app.modules.tickets.models import QueueTicket
from app.modules.tickets.repository import lock_institute
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data

NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


def seed(db, institute):
    db.add(Institute(id="crm_foreign", region_id=db.get(Institute, institute).region_id,
        name="Foreign fixture", city="Test"))
    db.flush()
    db.add(Customer(id="customer_foreign", institute_id="crm_foreign", display_name="Same Name",
        phone="123456", search_name="same name", phone_digits="123456", idempotency_key="foreign",
        creation_fingerprint="f", created_at=NOW, created_by="actor"))
    for identity in ("customer_crm", "customer_other"):
        db.add(Customer(id=identity, institute_id=institute, display_name="Same Name",
            phone="123456", search_name="same name", phone_digits="123456",
            idempotency_key=identity, creation_fingerprint="f", created_at=NOW, created_by="actor"))
    db.flush()
    db.add(QueueTicket(id="foreign_scoped_ticket", institute_id="crm_foreign", ticket_number="F",
        customer_id="customer_crm", status="paid", arrival_time=NOW-timedelta(hours=2),
        paid_at=NOW-timedelta(hours=1), currency="CHF", total_amount=Decimal("999")))
    for index in range(105):
        db.add(QueueTicket(id=f"crm_{index}", institute_id=institute, ticket_number=str(index),
            customer_id="customer_crm", status="paid", arrival_time=NOW-timedelta(hours=2),
            paid_at=NOW-timedelta(hours=1), currency="CHF", total_amount=Decimal("1.01")))
    for identity, customer, status, paid, amount, currency in (
        ("other", "customer_other", "paid", NOW-timedelta(hours=1), "999", "CHF"),
        ("opaque", "historical_opaque", "paid", NOW-timedelta(hours=1), "999", "CHF"),
        ("unpaid", "customer_crm", "waiting", NOW-timedelta(hours=1), "999", "CHF"),
        ("unknown_date", "customer_crm", "paid", None, "999", "CHF"),
        ("at_end", "customer_crm", "paid", NOW, "999", "CHF"),
        ("before", "customer_crm", "paid", NOW-timedelta(days=2), "999", "CHF"),
        ("eur", "customer_crm", "paid", NOW-timedelta(hours=1), "2.03", "EUR"),
        ("missing", "customer_crm", "paid", NOW-timedelta(hours=1), None, "EUR"),
        ("negative", "customer_crm", "paid", NOW-timedelta(hours=1), "-1", "EUR"),
        ("unknown_currency", "customer_crm", "paid", NOW-timedelta(hours=1), "1", None)):
        db.add(QueueTicket(id=identity, institute_id=institute, ticket_number=identity,
            customer_id=customer, status=status, arrival_time=NOW-timedelta(days=3),
            paid_at=paid, currency=currency, total_amount=Decimal(amount) if amount is not None else None))
    db.commit()


def exercise(engine, institute, monkeypatch):
    monkeypatch.setattr(billing, "utcnow", lambda: NOW)
    with Session(engine) as db:
        seed(db, institute)
        statements = []
        def track(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)
        event.listen(engine, "before_cursor_execute", track)
        try:
            result = billing.read(db, institute, "customer_crm", NOW-timedelta(days=1), NOW)
        finally:
            event.remove(engine, "before_cursor_execute", track)
        assert len(statements) == 3  # lock, registered customer, streamed cohort
        assert result.closed_tickets == 109
        chf, eur = result.currencies
        assert chf.closed_tickets == 105 and chf.known_gross_minor == "10605"
        assert chf.recorded_average_basket_minor.numerator == "10605"
        assert chf.recorded_average_basket_minor.denominator == 105
        assert eur.recorded_average_basket_minor is None
        assert (eur.known_amount_tickets, eur.missing_amount_tickets, eur.invalid_amount_tickets) == (1, 1, 1)
        assert result.unknown_currency_tickets == 1 and result.recorded_recency_us == "3600000000"
        zone = timezone(timedelta(hours=2))
        alias = billing.read(db, institute, "customer_crm",
            (NOW-timedelta(days=1)).astimezone(zone), NOW.astimezone(zone))
        assert alias.closed_tickets == result.closed_tickets
        assert alias.currencies == result.currencies
        for customer in ("historical_opaque", "missing_customer", "customer_foreign"):
            with pytest.raises(HTTPException) as error:
                billing.read(db, institute, customer, NOW-timedelta(days=1), NOW)
            assert error.value.status_code == 404
        with pytest.raises(HTTPException) as error:
            billing.read(db, "crm_foreign", "customer_crm", NOW-timedelta(days=1), NOW)
        assert error.value.status_code == 404


def test_sqlite_complete_registered_cohort(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    exercise(main_module.engine, institute, monkeypatch)


def test_postgres_complete_registered_cohort(postgres_flow, monkeypatch):
    engine, institute, _, _ = postgres_flow
    exercise(engine, institute, monkeypatch)


def test_signed_api_scope_roles_and_explicit_window(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    monkeypatch.setattr(billing, "utcnow", lambda: NOW)
    with Session(main_module.engine) as db:
        seed(db, institute)
    path = f"/api/v1/customers/institutes/{institute}/customer_crm/billing"
    params = {"start": (NOW-timedelta(days=1)).isoformat(), "end": NOW.isoformat()}
    headers = _auth_headers("responsable_institut", institute)
    response = client.get(path, headers=headers, params=params)
    assert response.status_code == 200, response.text
    assert response.json()["closed_tickets"] == 109
    assert response.json()["predicted_clv"] is None
    for role, tenant in (("accueil", institute), ("collaboratrice", institute),
        ("direction", institute), ("responsable_institut", "foreign"), ("responsable_institut", None)):
        assert client.get(path, headers=_auth_headers(role, tenant), params=params).status_code == 403
    assert client.get(path, params=params).status_code == 403
    for changes in ({"start": "2026-10-06"}, {"start": "1"}, {"start": "2026-10-06T12:00:00"},
        {"end": (NOW+timedelta(microseconds=1)).isoformat()}, {"start": NOW.isoformat()}):
        assert client.get(path, headers=headers, params={**params, **changes}).status_code == 400
    assert client.get(path, headers=headers).status_code == 422
    assert client.get(path.replace("customer_crm", "historical_opaque"), headers=headers, params=params).status_code == 404


def test_amount_diagnostics_ignore_decimal_context_and_refuse_float():
    with localcontext() as context:
        context.prec = 2
        for amount, expected in (("99999999.99", "9999999999"), ("1.0100", "101"),
            ("1E+2", "10000"), ("-0.00", "0")):
            assert billing.amount_fact(Decimal(amount)) == (expected, "known")
        for amount in ("0.001", "NaN", "Infinity", "-1", "100000000", "bad", True, 1.01):
            assert billing.amount_fact(amount) == (None, "invalid")
    assert billing.amount_fact(None) == (None, "missing")


def test_postgres_billing_holds_shared_lock_until_snapshot_complete(postgres_flow, monkeypatch):
    engine, institute, _, _ = postgres_flow
    monkeypatch.setattr(billing, "utcnow", lambda: NOW)
    with Session(engine) as db:
        seed(db, institute)
    paused, release, attempted = Event(), Event(), Event()

    def observe(connection, cursor, statement, parameters, context, executemany):
        if connection.info.get("crm_reader") and "FROM queue_tickets" in statement and not paused.is_set():
            paused.set()
            assert release.wait(timeout=15)
        if not connection.info.get("crm_reader") and "FROM institutes" in statement and "FOR UPDATE" in statement:
            attempted.set()

    def reader():
        with Session(engine) as db:
            connection = db.connection()
            connection.info["crm_reader"] = True
            try:
                return billing.read(db, institute, "customer_crm", NOW-timedelta(days=1), NOW)
            finally:
                connection.info.pop("crm_reader", None)

    def writer():
        with Session(engine) as db:
            lock_institute(db, institute)
            db.get(QueueTicket, "crm_0").total_amount = Decimal("9.99")
            db.commit()

    event.listen(engine, "before_cursor_execute", observe)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            reading = pool.submit(reader)
            assert paused.wait(timeout=10)
            writing = pool.submit(writer)
            assert attempted.wait(timeout=10)
            try:
                with pytest.raises(TimeoutError):
                    writing.result(timeout=0.2)
            finally:
                release.set()
            snapshot = reading.result(timeout=15)
            writing.result(timeout=15)
        assert snapshot.currencies[0].known_gross_minor == "10605"
        with Session(engine) as db:
            assert billing.read(db, institute, "customer_crm", NOW-timedelta(days=1), NOW).currencies[0].known_gross_minor == "11503"
    finally:
        release.set()
        event.remove(engine, "before_cursor_execute", observe)
