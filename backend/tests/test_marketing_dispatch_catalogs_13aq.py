import json
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.marketing import dispatch_intents, dispatch_catalogs, campaign_originals, contact_originals
from app.modules.marketing.models import DispatchIntent, DispatchOutcome
from test_marketing_dispatch_outcomes_13aj import fixture
from test_marketing_contact_originals_13y import body as contact_body
from test_marketing_campaign_originals_13i import body as campaign_body
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers


def exercise(engine, institute, monkeypatch):
    first = fixture(engine, institute, monkeypatch)
    account = first.submission.account.model_dump()
    accounts = [account] + [{**account, "account_id":f"a-{index:03}"} for index in range(24)]
    accounts += [{**account, "institute_id":"foreign", "account_id":"foreign-account"}, {**account, "channel":"sms", "account_id":"sms-account"}]
    monkeypatch.setattr(dispatch_intents.settings, "MARKETING_ACCOUNTS_JSON", json.dumps(accounts))
    with Session(engine) as db:
        one = dispatch_catalogs.accounts(db, institute, "email"); two = dispatch_catalogs.accounts(db, institute, "email", 20)
        assert one.total == two.total == 25 and len(one.items) == 20 and len(two.items) == 5
        assert [a.account_id for a in one.items + two.items] == sorted(a["account_id"] for a in accounts if a["institute_id"] == institute and a["channel"] == "email")
        assert all(a.institute_id == institute and a.channel == "email" for a in one.items + two.items)
        assert dispatch_catalogs.accounts(db, institute, "email", 25).items == ()
        assert dispatch_catalogs.accounts(db, institute, "push").total == 0
        contact = contact_originals.create(db, institute, "aud_054", contact_body(institute, "aud_054", "second-contact"), "manager")
        current = campaign_originals.require(db, institute, first.request.expected_revision_id)
        originals = [first]
        for index in range(12):
            audience = current.revision.content.audience.id; root = current.revision.campaign_id
            edited = campaign_originals.execute(db, institute, campaign_body(audience, f"edit-{index}", root, current.revision.id, "edit"), "manager")
            review = campaign_originals.execute(db, institute, campaign_body(audience, f"review-{index}", root, edited.revision.id, "review"), "manager")
            current = campaign_originals.execute(db, institute, campaign_body(audience, f"approve-{index}", root, review.revision.id, "approve"), "manager")
            for customer, contact_id in [("aud_000", first.request.expected_contact_id), ("aud_054", contact.id)]:
                request = first.request.model_copy(update={"expected_revision_id":current.revision.id, "customer_id":customer,
                    "expected_contact_id":contact_id, "idempotency_key":f"intent-{index}-{customer}"})
                originals.append(dispatch_intents.prepare(db, institute, request, "manager"))
        page = dispatch_catalogs.intents(db, institute, root); last = dispatch_catalogs.intents(db, institute, root, 20)
        assert page.total == last.total == 25 and len(page.items) == 20 and len(last.items) == 5
        assert {o.id for o in page.items + last.items} == {o.id for o in originals}
        assert list(page.items + last.items) == sorted(originals, key=lambda original: (original.created_at, original.id))
        assert dispatch_catalogs.intents(db, institute, root, 25).items == ()
        assert dispatch_intents.require(db, institute, first.id) == first
        assert db.scalar(select(func.count()).select_from(DispatchIntent)) == 25
        assert db.scalar(select(func.count()).select_from(DispatchOutcome)) == 0
        with pytest.raises(HTTPException): dispatch_catalogs.intents(db, "foreign", root)
        for offset, limit in [(-1,20),(0,51),(True,20),(0,False)]:
            with pytest.raises(HTTPException): dispatch_catalogs.intents(db, institute, root, offset, limit)
        with monkeypatch.context() as config:
            config.setattr(dispatch_intents.settings, "MARKETING_ACCOUNTS_JSON", json.dumps(accounts + [account]))
            with pytest.raises(HTTPException): dispatch_catalogs.accounts(db, institute, "email")
        with monkeypatch.context() as config:
            config.setattr(dispatch_intents.settings, "MARKETING_ACCOUNTS_JSON", json.dumps([{**account, "secret":"must-not-leak"}]))
            with pytest.raises(HTTPException) as error: dispatch_catalogs.accounts(db, institute, "email")
            assert error.value.__cause__ is None and error.value.__suppress_context__
            assert "must-not-leak" not in str(error.value)
        row = db.get(DispatchIntent, first.id); fingerprint = row.request_fingerprint
        row.request_fingerprint = "0" * 64; db.commit()
        with pytest.raises(HTTPException): dispatch_catalogs.intents(db, institute, root, 0, 50)
        row.request_fingerprint = fingerprint; db.commit()
        assert dispatch_intents.require(db, institute, first.id) == first
    return first, account


def test_sqlite_dispatch_selection_pages_and_signed_scope(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client); first, account = exercise(main_module.engine, institute, monkeypatch)
    base = f"/api/v1/marketing/institutes/{institute}"
    paths = ["/dispatch-accounts?channel=email", f"/campaigns/{first.request.campaign_id}/dispatch-intents"]
    headers = _auth_headers("responsable_institut", institute)
    for path in paths:
        response = client.get(base + path, headers=headers)
        assert response.status_code == 200 and response.json()["total"] == 25 and len(response.json()["items"]) == 20
        separator = "&" if "?" in path else "?"
        assert client.get(base + path + separator + "limit=51", headers=headers).status_code == 422
        assert client.get(base + path).status_code == 403
        for role, owner in [("accueil",institute),("collaboratrice",institute),("responsable_institut","foreign")]:
            assert client.get(base + path, headers=_auth_headers(role, owner)).status_code == 403
    assert client.get(base + "/dispatch-accounts?channel=unknown", headers=headers).status_code == 422
    assert client.get(base + "/dispatch-accounts", headers=headers).status_code == 422
    value = client.get(base + "/dispatch-accounts?channel=email&limit=1", headers=headers).json()["items"][0]
    assert set(value) == set(account) and "secret" not in value
    monkeypatch.setattr(dispatch_intents.settings, "MARKETING_ACCOUNTS_JSON", "[]")
    assert client.get(base + "/dispatch-accounts?channel=email", headers=headers).json()["total"] == 0
    assert client.get(base + paths[1], headers=headers).json()["total"] == 25


def test_postgres_dispatch_selection_pages(postgres_flow, monkeypatch):
    exercise(postgres_flow[0], postgres_flow[1], monkeypatch)
