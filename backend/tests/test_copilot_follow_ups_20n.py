from datetime import datetime, timedelta
import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session
import app.main as main_module
from app.database.session import get_db
from app.modules.copilot import query, opportunities
from app.modules.appointments.models import BookingEvent
from app.modules.waitlist.originals import fingerprint
from test_revenue_closures_14c import exercise as booking_sources
from test_revenue_walk_in_cancellations_14h import exercise as walk_in_sources
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers


def exercise(client, engine, institute, employee, service, monkeypatch):
    bookings = booking_sources(engine, institute, employee, service, monkeypatch)
    walk_ins = walk_in_sources(engine, institute, service, monkeypatch)
    ui = {"opportunity_source": "closures", "start": bookings.window.start.isoformat(), "end": bookings.window.end.isoformat()}
    def post(selection=ui, role="responsable_institut"):
        return client.post("/api/v1/copilot/query", headers=_auth_headers(role, institute),
            json={"message": "Examiner les opportunites de revenus", "ui_context": selection})
    statements = []
    def collect(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine, "before_cursor_execute", collect)
    try:
        response = post()
        assert response.status_code == 200, response.text
        data = response.json()
        evidence, result = data["evidence"], data["evidence"]["result"]
        assert data["capability"] == "REVENUE_OPPORTUNITIES" and data["actions"] == []
        assert result["booking_total"] == 25 and result["walk_in_total"] == 26
        assert len(result["booking_candidates"]) == len(result["walk_in_candidates"]) == 20
        assert result["bookings"]["source_digest"] == fingerprint(bookings.model_dump(mode="json"))
        assert result["walk_ins"]["source_digest"] == fingerprint(walk_ins.model_dump(mode="json"))
        assert result["walk_ins"]["retained_amounts"] == walk_ins.model_dump(mode="json")["retained_amounts"]
        assert result["booking_candidates"] == [dict(event_id=row.evidence.event_id, appointment_id=row.evidence.appointment_id,
            type=row.type, occurred_at=row.evidence.model_dump(mode="json")["occurred_at"], estimated_value=None) for row in bookings.opportunities]
        assert [row["retained_value"] for row in result["walk_in_candidates"]] == [row.model_dump(mode="json")["estimated_value"] for row in walk_ins.opportunities]
        assert result["estimated_recovered_revenue"] is None and not result["delivery_authorized"] and not result["action_executed"]
        assert evidence["fingerprint"] == fingerprint({k: v for k, v in evidence.items() if k != "fingerprint"})
        for field in ('"customer_id"', '"actor_id"', '"customer_name"', '"before"', '"after"', '"lines"', '"original"'):
            assert field not in response.text
    finally:
        event.remove(engine, "before_cursor_execute", collect)
    assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP"}
    assert post(role="accueil").status_code == 403
    assert post({"opportunity_source": "closures"}).json()["status"] == "clarification"
    assert post({**ui, "service_id": service}).status_code == 400
    assert post({**ui, "opportunity_source": "rebooking"}).status_code == 400
    assert post({**ui, "opportunity_source": "capacity"}).status_code == 400
    assert post({**ui, "start": 1}).status_code == 422
    assert post({**ui, "end": ui["start"]}).status_code == 400
    assert post({**ui, "end": (bookings.window.captured_at+timedelta(days=1)).isoformat()}).status_code == 400
    for changed in ({"institute_id": "foreign"}, {"booking_total": 0}, {"action_executed": 0}):
        with pytest.raises(ValueError):
            opportunities.FollowUps.model_validate({**result, **changed})
    discovered = client.get("/api/v1/copilot/capabilities", headers=_auth_headers("responsable_institut", institute))
    assert discovered.status_code == 200
    assert "recorded_closure_follow_up" in discovered.text
    query.OpportunitySelection.model_validate(ui)
    with pytest.raises(ValueError):
        query.OpportunitySelection.model_validate({**ui, "service_id": service})
    later_capture = walk_ins.window.captured_at + timedelta(minutes=1)
    monkeypatch.setattr(opportunities.walk_in_cancellations, "utcnow", lambda: later_capture)
    staggered = post().json()["evidence"]
    assert datetime.fromisoformat(staggered["captured_at"]) == later_capture
    assert datetime.fromisoformat(staggered["result"]["bookings"]["window"]["captured_at"]) == bookings.window.captured_at
    assert datetime.fromisoformat(staggered["result"]["walk_ins"]["window"]["captured_at"]) == later_capture
    with Session(engine) as db:
        off_page = db.scalar(select(BookingEvent).where(BookingEvent.institute_id == institute)
            .order_by(BookingEvent.occurred_at, BookingEvent.id).offset(24))
        original = dict(off_page.after)
        off_page.after = {**original, "customer_id": "substituted"}
        db.commit()
        assert post().status_code == 400
        off_page.after = original
        db.commit()
    assert post().status_code == 200


def test_sqlite_closure_follow_ups(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    exercise(client, main_module.engine, institute, employees[0]["id"], services[0]["id"], monkeypatch)


def test_postgres_closure_follow_ups(client, postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    def database():
        with Session(engine) as db:
            yield db
    main_module.app.dependency_overrides[get_db] = database
    monkeypatch.setattr(main_module, "engine", engine)
    exercise(client, engine, institute, employee, service, monkeypatch)
