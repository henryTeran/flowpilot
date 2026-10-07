"""Opt-in actual retained conversion vectors; isolated SQLite/fake adapter only."""
import json
from datetime import timedelta
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.marketing import conversion_originals, conversion_catalogs
from app.modules.marketing import conversion_tickets
from test_marketing_conversion_originals_13az import setup
from test_ticket_workflow import _bootstrap_reference_data
from test_crm_billing_12b import NOW


def test_export_retained_conversion_contracts(client, monkeypatch):
    institute, _, _ = _bootstrap_reference_data(client)
    request = setup(main_module.engine, institute, monkeypatch)
    monkeypatch.setattr(conversion_catalogs, "utcnow", lambda: NOW + timedelta(days=4))
    monkeypatch.setattr(conversion_tickets, "utcnow", lambda: NOW + timedelta(days=4))
    with Session(main_module.engine) as db:
        linked = conversion_originals.execute(db, institute, request, "manager")
        campaign = linked.attribution.intent.request.campaign_id
        window = conversion_catalogs.Request(start=request.selection.start, end=request.selection.end)
        report = conversion_catalogs.report(db, institute, campaign, window)
        page = conversion_catalogs.current_links(db, institute, campaign, window)
        retracted = conversion_originals.execute(db, institute, conversion_originals.Request(action="retracted",
            ticket_id=request.ticket_id, expected_previous_id=linked.id, selection=None,
            reason="Explicit vector retraction", idempotency_key="vector-retraction"), "other-manager")
        empty = conversion_catalogs.report(db, institute, campaign, window)
        audit = conversion_originals.audit(db, institute, request.ticket_id)
        ticket_request = conversion_tickets.Request(intent_id=request.selection.intent_id, expected_fingerprint=request.selection.expected_fingerprint,
            accepted_outcome_id=request.selection.accepted_outcome_id, start=window.start, end=window.end)
        tickets = conversion_tickets.read(db, institute, ticket_request)
        vector = dict(institute_id=institute, campaign_id=campaign, window=window.model_dump(mode="json"),
            linked=linked.model_dump(mode="json"), retracted=retracted.model_dump(mode="json"),
            report=report.model_dump(mode="json"), empty_report=empty.model_dump(mode="json"),
            page=page.model_dump(mode="json"), audit=audit.model_dump(mode="json"), tickets=tickets.model_dump(mode="json"))
    print("FLOWPILOT_EXPORT=" + json.dumps(vector, ensure_ascii=True, separators=(",", ":")))
