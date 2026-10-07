from datetime import timedelta
import copy

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.marketing import campaign_originals as campaigns, contact_originals as contacts, recipient_observations as observations
from test_crm_billing_12b import NOW
from test_marketing_audience_originals_13e import exercise as capture_fixture
from test_marketing_campaign_originals_13i import body as campaign_body
from test_marketing_contact_originals_13y import body as contact_body
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def setup(engine, institute, monkeypatch):
    audience = capture_fixture(engine, institute, monkeypatch)
    at = NOW + timedelta(microseconds=3)
    monkeypatch.setattr(campaigns, "utcnow", lambda: at)
    monkeypatch.setattr(contacts, "utcnow", lambda: at)
    with Session(engine) as db:
        draft = campaigns.execute(db, institute, campaign_body(audience.id), "manager")
        root = draft.revision.campaign_id
        review = campaigns.execute(db, institute, campaign_body(audience.id, "review", root, draft.revision.id, "review"), "manager")
        approved = campaigns.execute(db, institute, campaign_body(audience.id, "approve", root, review.revision.id, "approve"), "manager")
        declared = contacts.create(db, institute, "aud_000", contact_body(institute, "aud_000", "contact"), "manager")
    return audience, approved, declared


def exercise(engine, institute, monkeypatch):
    audience, approved, declared = setup(engine, institute, monkeypatch)
    root, expected = approved.revision.campaign_id, approved.revision.id
    calls = []
    def clock(): calls.append(True); return NOW + timedelta(microseconds=4)
    monkeypatch.setattr(observations, "utcnow", clock)
    with Session(engine) as db:
        first = observations.read(db, institute, root, expected, 0, 1)
        assert calls == [True] and first.total == 2 and len(first.items) == 1
        assert first.items[0].customer.customer_id == "aud_000" and first.items[0].original == declared
        assert first.items[0].reason == "declared_eligible" and first.items[0].eligible_by_current_declaration
        assert not first.complete_campaign_evaluation and not first.delivery_authorized and not first.external_message_sent
        second = observations.read(db, institute, root, expected, 1, 1)
        assert second.items[0].customer.customer_id == "aud_054" and second.items[0].reason == "declaration_absent"
        # Legacy grant retained in the audience is not a fresh destination declaration.
        assert audience.summary.eligible_count == 2 and not second.items[0].eligible_by_current_declaration
        assert observations.Page.model_validate_json(first.model_dump_json()) == first
        for changes in [{"total": 3}, {"expected_revision_id": "stale"}, {"institute_id": "foreign"}, {"offset": 1},
                        {"complete_campaign_evaluation": True}, {"delivery_authorized": True}]:
            with pytest.raises(ValidationError): observations.Page.model_validate({**first.model_dump(), **changes})
        for changes in [{"reason": "permission_refused"}, {"eligible_by_current_declaration": False}, {"eligible_by_current_declaration": 1}]:
            altered = copy.deepcopy(first.model_dump()); altered["items"][0].update(changes)
            with pytest.raises(ValidationError): observations.Page.model_validate(altered)
        altered = copy.deepcopy(first.model_dump()); altered["campaign"]["request"]["reason"] = "Forged original reason"
        with pytest.raises(ValidationError): observations.Page.model_validate(altered)
        for offset, limit in [(-1, 1), (0, 0), (0, 51), (True, 1), (0, False)]:
            with pytest.raises(HTTPException): observations.read(db, institute, root, expected, offset, limit)
        assert observations.read(db, institute, root, expected, 2, 1).items == ()
        with pytest.raises(HTTPException): observations.read(db, institute, root, "stale")
        with pytest.raises(HTTPException): observations.read(db, "marketing_foreign", root, expected)
        monkeypatch.setattr(contacts, "utcnow", lambda: NOW + timedelta(microseconds=5))
        withdrawn = contacts.create(db, institute, "aud_000", contact_body(institute, "aud_000", "withdraw", declared.id, "refused"), "manager")
        # The same head can be future relative to an explicitly sampled earlier clock.
        assert observations.read(db, institute, root, expected, 0, 1).items[0].reason == "future_declaration"
        monkeypatch.setattr(observations, "utcnow", lambda: withdrawn.created_at)
        current = observations.read(db, institute, root, expected, 0, 1)
        assert current.items[0].reason == "permission_refused" and not current.items[0].eligible_by_current_declaration
        assert contacts.require(db, institute, "aud_000", declared.id) == declared
        assert campaigns.require(db, institute, approved.revision.id) == approved
        edited = campaigns.execute(db, institute, campaign_body(audience.id, "edit", root, expected, "edit"), "manager")
        with pytest.raises(HTTPException): observations.read(db, institute, root, expected)
        assert observations.read(db, institute, root, edited.revision.id).items[0].reason == "campaign_not_approved"
    return root, edited.revision.id


def test_sqlite_recipient_pages_recheck_current_sources_and_signed_access(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    root, expected = exercise(main_module.engine, institute, monkeypatch)
    path = f"/api/v1/marketing/institutes/{institute}/campaigns/{root}/recipient-observations"
    headers = _auth_headers("responsable_institut", institute)
    reply = client.get(path, params={"expected_revision_id": expected, "offset": 1, "limit": 1}, headers=headers)
    assert reply.status_code == 200, reply.text
    assert reply.json()["items"][0]["customer"]["customer_id"] == "aud_054"
    for params in [{}, {"expected_revision_id": expected, "offset": -1}, {"expected_revision_id": expected, "limit": 51}]:
        assert client.get(path, params=params, headers=headers).status_code == 422
    assert client.get(path, params={"expected_revision_id": "stale"}, headers=headers).status_code == 400
    for role, owner in [("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")]:
        assert client.get(path, params={"expected_revision_id": expected}, headers=_auth_headers(role, owner)).status_code == 403
    assert client.get(path, params={"expected_revision_id": expected}).status_code == 403


def test_postgres_recipient_pages_recheck_current_sources(postgres_flow, monkeypatch):
    exercise(postgres_flow[0], postgres_flow[1], monkeypatch)


def test_postgres_page_holds_institute_lock_against_permission_withdrawal(postgres_flow, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    from threading import Event
    from sqlalchemy import event
    engine, institute = postgres_flow[:2]
    _, approved, declared = setup(engine, institute, monkeypatch)
    sampled, release, writer_attempt = Event(), Event(), Event()
    def clock():
        sampled.set()
        assert release.wait(10), "Observation was not released"
        return NOW + timedelta(microseconds=4)
    monkeypatch.setattr(observations, "utcnow", clock)
    monkeypatch.setattr(contacts, "utcnow", lambda: NOW + timedelta(microseconds=5))
    def observe():
        with Session(engine) as db:
            return observations.read(db, institute, approved.revision.campaign_id, approved.revision.id, 0, 1)
    def withdraw():
        with Session(engine) as db:
            connection = db.connection()
            def attempted(conn, cursor, statement, parameters, context, executemany):
                if "FOR UPDATE" in statement: writer_attempt.set()
            event.listen(connection, "before_cursor_execute", attempted)
            try:
                return contacts.create(db, institute, "aud_000", contact_body(institute, "aud_000", "concurrent-withdraw", declared.id, "refused"), "manager")
            finally: event.remove(connection, "before_cursor_execute", attempted)
    with ThreadPoolExecutor(max_workers=2) as pool:
        reader = pool.submit(observe)
        try:
            assert sampled.wait(10)
            writer = pool.submit(withdraw)
            assert writer_attempt.wait(10)
            with pytest.raises(TimeoutError): writer.result(timeout=0.2)
        finally: release.set()
        observed = reader.result(timeout=15); withdrawn = writer.result(timeout=15)
    assert observed.items[0].original == declared and observed.items[0].eligible_by_current_declaration
    monkeypatch.setattr(observations, "utcnow", lambda: withdrawn.created_at)
    with Session(engine) as db:
        fresh = observations.read(db, institute, approved.revision.campaign_id, approved.revision.id, 0, 1)
        assert fresh.items[0].original == withdrawn and fresh.items[0].reason == "permission_refused"
