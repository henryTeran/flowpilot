from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import timedelta
from threading import Event

import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.crm import policies, profile
from app.modules.customers.models import Customer
from app.modules.tickets.models import QueueTicket
from test_crm_billing_12b import NOW, seed
from test_crm_policies_12d import body as policy_body
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def body(institute, key="original", previous=None, **changes):
    return policy_body(institute, key, previous,
        **dict(dict(at_risk_us=7200000000, dormant_us=14400000000), **changes))


def exercise(engine, institute, monkeypatch):
    monkeypatch.setattr(profile, "utcnow", lambda: NOW)
    monkeypatch.setattr(policies, "utcnow", lambda: NOW)
    with Session(engine) as db:
        seed(db, institute)
        absent = profile.read(db, institute, "customer_crm")
        assert absent.unavailable_reason == "policy_absent" and absent.segment is None
        assert absent.policy_original is None and absent.undated_paid_tickets == 1
        first = policies.create(db, institute, body(institute), "manager")
        statements = []
        def track(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)
        event.listen(engine, "before_cursor_execute", track)
        try:
            unknown = profile.read(db, institute, "customer_crm")
        finally:
            event.remove(engine, "before_cursor_execute", track)
        assert len(statements) == 6
        assert unknown.segment.state is None and unknown.segment.reason == "undated_closings"
        assert unknown.segment.billing.closed_tickets == 109
        assert unknown.segment.billing.window.captured_at == unknown.captured_at
        db.get(QueueTicket, "unknown_date").status = "waiting"
        db.commit()
        known = profile.read(db, institute, "customer_crm")
        assert known.segment.state == "VIP" and known.policy_original == first
        assert known.segment.policy == first.policy
        assert known.segment.billing.window.end == known.captured_at
        assert known.segment.billing.window.start == NOW-timedelta(days=1)
        assert known.undated_paid_tickets == known.future_paid_tickets == 0
        second = policies.create(db, institute, body(institute, "correction", first.id,
            vip_gross_minor="999999"), "manager")
        updated = profile.read(db, institute, "customer_crm")
        assert updated.policy_original == second
        assert updated.segment.state is None and updated.segment.reason == "uncertain_vip_gross"
        assert known.policy_original == first  # previously captured evidence remains pinned
        monkeypatch.setattr(profile, "utcnow", lambda: NOW-timedelta(microseconds=1))
        assert profile.read(db, institute, "customer_crm").unavailable_reason == "future_policy"
        monkeypatch.setattr(profile, "utcnow", lambda: NOW)
        db.get(Customer, "customer_crm").created_at = NOW+timedelta(microseconds=1)
        db.commit()
        assert profile.read(db, institute, "customer_crm").unavailable_reason == "future_registration"
        db.get(Customer, "customer_crm").created_at = NOW
        db.get(QueueTicket, "at_end").paid_at = NOW+timedelta(microseconds=1)
        db.commit()
        future = profile.read(db, institute, "customer_crm")
        assert future.future_paid_tickets == 1 and future.unavailable_reason == "future_closings"
        assert future.segment is None
        db.get(QueueTicket, "at_end").status = "waiting"
        db.commit()
        policies.create(db, institute, body(institute, "overflow", second.id,
            observation_us=10**30), "manager")
        assert profile.read(db, institute, "customer_crm").unavailable_reason == "unrepresentable_horizon"
        for customer in ("customer_foreign", "historical_opaque", "customer_missing"):
            with pytest.raises(HTTPException) as error:
                profile.read(db, institute, customer)
            assert error.value.status_code == 404


def test_sqlite_current_policy_sources_and_unknown_diagnostics(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    exercise(main_module.engine, institute, monkeypatch)


def test_postgres_current_policy_sources_and_unknown_diagnostics(postgres_flow, monkeypatch):
    engine, institute, _, _ = postgres_flow
    exercise(engine, institute, monkeypatch)


def test_signed_segment_api_scope_and_server_horizon(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    monkeypatch.setattr(profile, "utcnow", lambda: NOW)
    monkeypatch.setattr(policies, "utcnow", lambda: NOW)
    with Session(main_module.engine) as db:
        seed(db, institute)
        policies.create(db, institute, body(institute), "manager")
    path = f"/api/v1/crm/institutes/{institute}/customers/customer_crm/segment"
    headers = _auth_headers("responsable_institut", institute)
    response = client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["segment"]["reason"] == "undated_closings"
    assert result["policy_original"]["actor_id"] == "manager"
    assert result["complete_customer_history"] is False
    for role, tenant in (("accueil", institute), ("collaboratrice", institute),
        ("direction", institute), ("responsable_institut", "foreign"), ("responsable_institut", None)):
        assert client.get(path, headers=_auth_headers(role, tenant)).status_code == 403
    assert client.get(path).status_code == 403
    assert client.get(path.replace("customer_crm", "customer_foreign"), headers=headers).status_code == 404


def test_postgres_policy_correction_waits_for_entire_segment_snapshot(postgres_flow, monkeypatch):
    engine, institute, _, _ = postgres_flow
    monkeypatch.setattr(profile, "utcnow", lambda: NOW)
    monkeypatch.setattr(policies, "utcnow", lambda: NOW)
    with Session(engine) as db:
        seed(db, institute)
        db.get(QueueTicket, "unknown_date").status = "waiting"
        db.commit()
        first = policies.create(db, institute, body(institute), "manager")
    paused, release, attempted = Event(), Event(), Event()
    def observe(connection, cursor, statement, parameters, context, executemany):
        if connection.info.get("segment_reader") and "FROM queue_tickets" in statement and not paused.is_set():
            paused.set()
            assert release.wait(timeout=15)
        if not connection.info.get("segment_reader") and "FROM institutes" in statement and "FOR UPDATE" in statement:
            attempted.set()
    def reader():
        with Session(engine) as db:
            connection = db.connection()
            connection.info["segment_reader"] = True
            try:
                return profile.read(db, institute, "customer_crm")
            finally:
                connection.info.pop("segment_reader", None)
    def writer():
        with Session(engine) as db:
            return policies.create(db, institute, body(institute, "correction", first.id,
                vip_gross_minor="999999"), "manager")
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
            correction = writing.result(timeout=15)
        assert snapshot.policy_original == first and snapshot.segment.state == "VIP"
        with Session(engine) as db:
            current = profile.read(db, institute, "customer_crm")
            assert current.policy_original == correction
            assert current.segment.reason == "uncertain_vip_gross"
    finally:
        release.set()
        event.remove(engine, "before_cursor_execute", observe)
