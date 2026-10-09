from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main
from app.database.session import get_db
from app.modules.marketing import campaign_originals as originals, templates
from app.modules.marketing.models import TemplateOriginal, CampaignHead
from app.modules.copilot import marketing
from app.modules.base.read_capabilities import Principal
from test_marketing_audience_originals_13e import exercise as capture_fixture
from test_marketing_templates_13h import body as template_body
from test_crm_billing_12b import NOW
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers


def exercise(client, engine, institute, monkeypatch):
    audience = capture_fixture(engine, institute, monkeypatch)
    monkeypatch.setattr(templates, "utcnow", lambda: NOW)
    monkeypatch.setattr(originals, "utcnow", lambda: NOW + timedelta(microseconds=3))
    with Session(engine) as db:
        template = templates.create(db, institute, template_body(), "manager")
    headers = _auth_headers("responsable_institut", institute)
    selection = dict(audience_id=audience.id, template_original_id=template.id)
    request = dict(message="Preparer un brouillon de campagne marketing", ui_context=selection)
    path = "/api/v1/copilot"
    writes = []
    def observe(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE"}:writes.append(statement)
    event.listen(engine, "before_cursor_execute", observe)
    try:
        response = client.post(path+"/prepare-preview/marketing", headers=headers, json=request)
        assert response.status_code == 200, response.text
        preview = response.json()
        assert preview["recipient_count"] == 2 and not writes
        for private in ("aud_000", "aud_054", template.content.body, '"customer_ids"', '"body"'):
            assert private not in response.text
    finally:event.remove(engine, "before_cursor_execute", observe)
    body = {**request, "expected_state_fingerprint":preview["state_fingerprint"],
        "reason":"Reviewed exact draft", "idempotency_key":"copilot-draft"}
    def prepare(value=body, role="responsable_institut", owner=institute):
        return client.post(path+"/prepare/marketing", headers=_auth_headers(role, owner), json=value)
    assert prepare({**body,"expected_state_fingerprint":"0"*64}).status_code == 400
    assert prepare({**body,"message":"Preparer la creation d'un rendez-vous"}).status_code == 400
    assert prepare(role="accueil").status_code == 403
    assert prepare(owner="foreign").status_code == 404
    assert prepare({**body,"ui_context":{**selection,"body":"injected"}}).status_code == 422
    assert prepare({**body,"idempotency_key":" padded "}).status_code == 422
    with Session(engine) as db:
        row = db.get(TemplateOriginal, template.id)
        original_content, original_request = row.content, row.request
        row.content = {**row.content,"body":"Changed retained source"}
        row.request = {**row.request,"content":row.content}
        db.commit()
    assert prepare().status_code == 400  # coherent altered source differs from reviewed digest
    with Session(engine) as db:
        row = db.get(TemplateOriginal, template.id)
        row.content, row.request = original_content, original_request
        db.commit()
    result = prepare()
    assert result.status_code == 200, result.text
    value = result.json()
    assert value["state"] == "DRAFT" and value["state_fingerprint"] == preview["state_fingerprint"]
    with Session(engine) as db:
        retained = originals.require(db, institute, value["original_id"])
        assert retained.revision.content.body == template.content.body
        assert retained.revision.actor_id == "test-user"
        assert not retained.revision.delivery_authorized and not retained.revision.external_message_sent
    monkeypatch.setattr(originals, "utcnow", lambda: NOW - timedelta(days=1))
    assert prepare().json() == value
    assert prepare({**body,"reason":"Changed reason"}).status_code == 400
    assert prepare({**body,"expected_state_fingerprint":"0"*64}).status_code == 400
    assert prepare({**body,"idempotency_key":"new-key"}).status_code == 400
    def no_source(*args, **kwargs):raise AssertionError("Historical recovery recaptured template")
    monkeypatch.setattr(templates, "require", no_source)
    assert prepare().json() == value
    discovery = client.get(path+"/preparation-capabilities", headers=headers)
    assert discovery.status_code == 200, discovery.text
    capability = next(item for item in discovery.json() if item["name"] == "MARKETING_CAMPAIGN_DRAFT")
    assert capability["level"] == 2


def test_sqlite_marketing_preparation(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    exercise(client, main.engine, institute, monkeypatch)


def test_postgres_marketing_preparation(client, postgres_flow, monkeypatch):
    engine, institute = postgres_flow[:2]
    def database():
        with Session(engine) as db:yield db
    main.app.dependency_overrides[get_db] = database
    monkeypatch.setattr(main, "engine", engine)
    exercise(client, engine, institute, monkeypatch)


def test_postgres_draft_adapter_recovery_race_and_atomicity(postgres_flow, monkeypatch):
    engine, institute = postgres_flow[:2]
    audience = capture_fixture(engine, institute, monkeypatch)
    monkeypatch.setattr(templates, "utcnow", lambda: NOW)
    monkeypatch.setattr(originals, "utcnow", lambda: NOW+timedelta(microseconds=3))
    principal = Principal(actor_id="manager", institute_id=institute, role="responsable_institut")
    with Session(engine) as db:
        template = templates.create(db, institute, template_body(), "manager")
        request = dict(message="Preparer un brouillon de campagne marketing",
            ui_context=dict(audience_id=audience.id, template_original_id=template.id))
        preview = marketing.preview(db, principal, request)
        db.rollback()
    body = {**request,"reason":"Reviewed exact draft","idempotency_key":"racing-draft",
        "expected_state_fingerprint":preview.state_fingerprint}
    def run():
        with Session(engine) as db:return marketing.prepare(db, principal, body)
    with ThreadPoolExecutor(max_workers=2) as pool:
        one, two = [future.result(timeout=25) for future in [pool.submit(run),pool.submit(run)]]
    assert one == two
    with Session(engine) as db:
        assert originals.audit(db, institute, one.campaign_id).total == 1
        def fail(session, context, instances):
            if any(isinstance(row, CampaignHead) for row in session.new):
                raise RuntimeError("Injected draft head failure")
        event.listen(db, "before_flush", fail)
        try:
            with pytest.raises(RuntimeError, match="Injected"):
                marketing.prepare(db, principal, {**body,"idempotency_key":"rolled-back-draft"})
        finally:event.remove(db, "before_flush", fail)
        assert originals.original(db, institute, "rolled-back-draft") is None
        assert originals.current(db, institute, one.campaign_id).revision.id == one.original_id
