from datetime import timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.appointments import service as bookings, events
from app.modules.appointments.models import Appointment, BookingEvent
from app.modules.services.models import Service
from app.modules.revenue import closures
from test_revenue_billing_14a import NOW
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def exercise(engine, institute, employee, service, monkeypatch):
    for module in (closures, bookings, events):
        monkeypatch.setattr(module, "utcnow", lambda: NOW)
    with Session(engine) as db:
        for n in range(25):
            db.add(Appointment(id=f"closure-{n:02}", institute_id=institute, employee_id=employee, service_id=service,
                customer_name="Fixture", start_time=NOW-timedelta(days=1)+timedelta(hours=n),
                end_time=NOW-timedelta(days=1)+timedelta(hours=n, minutes=30), status="scheduled"))
        db.add(Appointment(id="closure-legacy", institute_id=institute, employee_id=employee, service_id=service,
            customer_name="Undated closure", start_time=NOW, end_time=NOW+timedelta(minutes=30), status="cancelled"))
        db.commit()
        for n in range(25):
            action = bookings.cancel_appointment if n % 2 == 0 else bookings.mark_appointment_no_show
            action(db, f"closure-{n:02}", "signed-manager")
        start, end = NOW-timedelta(seconds=1), NOW+timedelta(seconds=1)
        monkeypatch.setattr(closures, "utcnow", lambda: end)
        first = closures.read(db, institute, start, end)
        last = closures.read(db, institute, start, end, 20)
        assert first.page.total == last.page.total == first.unpriced_count == 25
        assert len(first.opportunities) == 20 and len(last.opportunities) == 5
        assert first.cancelled_count == 13 and first.no_show_count == 12
        assert first.institute_terminal_bookings_without_closure_event == 1
        assert all(row.estimated_value is None and row.evidence.retained_booking_price is None and not row.action_executed
            and row.evidence.actor_id == "signed-manager" for row in first.opportunities+last.opportunities)
        assert first.cancelled_revenue is first.no_show_revenue is None and not first.causal_loss_proven
        db.get(Service, service).price_passage = 999; db.commit()
        assert closures.read(db, institute, start, end).opportunities == first.opportunities
        assert closures.read(db, institute, start, NOW).page.total == 0  # event-time half-open boundary
        off_page = last.opportunities[-1].evidence.appointment_id
        event = db.scalar(select(BookingEvent).where(BookingEvent.appointment_id == off_page))
        original = dict(event.after)
        event.after = {**original, "customer_id": "substituted"}; db.commit()
        with pytest.raises(HTTPException): closures.read(db, institute, start, end, limit=1)  # corruption outside requested page
        event.after = original; db.commit()
        db.add(BookingEvent(id="duplicate-closure", institute_id=institute, appointment_id=event.appointment_id,
            event_type=event.event_type, actor_id=event.actor_id, occurred_at=NOW-timedelta(days=10), before=event.before, after=event.after))
        db.commit()
        with pytest.raises(HTTPException): closures.read(db, institute, start, end)
        db.delete(db.get(BookingEvent, "duplicate-closure")); db.commit()
        for offset, limit in ((-1,20), (0,51), (True,20)):
            with pytest.raises(HTTPException): closures.read(db, institute, start, end, offset, limit)
        with pytest.raises(HTTPException): closures.read(db, institute, start, end+timedelta(seconds=1))
        return first


def test_sqlite_actual_closure_services_and_signed_opportunity_read(client, monkeypatch):
    institute, employee, service, _, _ = setup(client)
    result = exercise(main_module.engine, institute, employee, service, monkeypatch)
    path = f"/api/v1/revenue/institutes/{institute}/booking-closures"
    params = dict(start=result.window.start.isoformat(), end=result.window.end.isoformat())
    headers = _auth_headers("responsable_institut", institute)
    response = client.get(path, params=params, headers=headers)
    assert response.status_code == 200 and response.json()["page"]["total"] == 25
    for role, owner in (("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")):
        assert client.get(path, params=params, headers=_auth_headers(role, owner)).status_code == 403
    assert client.get(path, params=params).status_code == 403
    assert client.get(path, params={**params, "start": "2026-01-01"}, headers=headers).status_code == 422
    assert client.get(path, params={**params, "limit": 51}, headers=headers).status_code == 422
    assert client.post(path, json=params, headers=headers).status_code == 405


def test_postgres_actual_closure_services(postgres_flow, monkeypatch):
    exercise(*postgres_flow, monkeypatch)


@pytest.mark.parametrize("change", ["foreign", "capture", "boundary", "terms", "execution", "current"])
def test_pure_opportunity_refuses_substituted_scope_time_and_booking_terms(change):
    from app.modules.revenue.billing import Window
    after = closures.BookingSnapshot(status="cancelled", employee_id="employee", service_id="service", customer_id=None,
        start_time=NOW, end_time=NOW+timedelta(minutes=30), booked_start_time=None, booked_end_time=None,
        actual_start_time=None, actual_end_time=None, checkout_ticket_id=None)
    before = after.model_copy(update={"status": "scheduled"})
    window = Window(institute_id="own", start=NOW-timedelta(seconds=1), end=NOW+timedelta(seconds=1), captured_at=NOW+timedelta(seconds=1))
    source = closures.Evidence(institute_id="own", event_id="event", appointment_id="appointment", event_type="cancelled",
        actor_id=None, occurred_at=NOW, captured_at=window.captured_at, before=before, after=after)
    opportunity = closures.verify(source, after, window)
    assert opportunity.estimated_value is None and opportunity.evidence.actor_id is None
    current = after
    if change == "foreign": source = source.model_copy(update={"institute_id": "foreign"})
    if change == "capture": source = source.model_copy(update={"captured_at": NOW})
    if change == "boundary": source = source.model_copy(update={"occurred_at": window.end})
    if change == "terms": source = source.model_copy(update={"before": before.model_copy(update={"service_id": "different"})})
    if change == "execution": source = source.model_copy(update={"before": before.model_copy(update={"actual_start_time": NOW}),
        "after": after.model_copy(update={"actual_start_time": NOW})}); current = source.after
    if change == "current": current = after.model_copy(update={"customer_id": "different"})
    with pytest.raises(ValueError): closures.verify(source, current, window)
    with pytest.raises(ValueError): closures.Opportunity.model_validate({**opportunity.model_dump(), "action_executed": 0})
