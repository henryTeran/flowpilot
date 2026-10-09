from datetime import timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main
from app.modules.marketing import campaign_originals as originals, campaigns, templates
from test_marketing_campaign_originals_13i import body
from test_marketing_audience_originals_13e import exercise as capture_fixture
from test_marketing_templates_13h import body as template_body
from test_crm_billing_12b import NOW
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data


def exercise(engine, institute, monkeypatch):
    audience = capture_fixture(engine, institute, monkeypatch)
    monkeypatch.setattr(originals, "utcnow", lambda: NOW + timedelta(microseconds=3))
    monkeypatch.setattr(templates, "utcnow", lambda: NOW)
    with Session(engine) as db:
        template = templates.create(db, institute, template_body(), "manager")
        content = originals.Content(channel=template.content.channel, origin=template.content.origin,
            subject=template.content.subject, body=template.content.body,
            audience_id=audience.id, template_original_id=template.id)
        request = body(audience.id, "preview-draft", content=content)
        writes = []
        def observe(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
                writes.append(statement)
        event.listen(engine, "before_cursor_execute", observe)
        try:
            preview = originals.preview_creation(db, institute, request, "manager")
            assert preview.content.audience.customer_ids == ("aud_000", "aud_054")
            assert preview.content_digest == campaigns.digest(preview.content)
            assert originals.original(db, institute, request.idempotency_key) is None
            for owner, candidate, actor in [
                ("foreign", request, "manager"),
                (institute, request, " "),
                (institute, body(audience.id, "review", "root", "revision", "review"), "manager"),
                (institute, request.model_copy(update={"content":content.model_copy(update={"body":"Different"})}), "manager"),
            ]:
                with pytest.raises(HTTPException):
                    originals.preview_creation(db, owner, candidate, actor)
            monkeypatch.setattr(originals, "utcnow", lambda: NOW - timedelta(days=1))
            with pytest.raises(HTTPException):
                originals.preview_creation(db, institute, request, "manager")
            assert writes == []
        finally:
            event.remove(engine, "before_cursor_execute", observe)
        monkeypatch.setattr(originals, "utcnow", lambda: preview.captured_at)
        retained = originals.execute(db, institute, request, "manager")
        assert retained.revision.content == preview.content
        assert retained.revision.state == "DRAFT"
        assert not retained.revision.delivery_authorized and not retained.revision.external_message_sent
        assert originals.execute(db, institute, request, "manager") == retained


def test_sqlite_draft_preview(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    exercise(main.engine, institute, monkeypatch)


def test_postgres_draft_preview(postgres_flow, monkeypatch):
    exercise(postgres_flow[0], postgres_flow[1], monkeypatch)
