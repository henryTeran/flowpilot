from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.modules.tickets.schemas import QueueTicketRead, QueueEventRead, TicketCreate
from app.modules.tickets.models import QueueEvent
from app.modules.tickets.routes import _read_ticket
from app.modules.tickets.service import create_queue_ticket
from app.shared.time import utcnow
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def dto(stamp):
    return QueueTicketRead(id="ticket", institute_id="inst", ticket_number="T-1",
        customer_id=None, subscription_id=None, assigned_employee_id=None, created_by_id=None,
        status="paid", arrival_time=stamp, estimated_start_time=stamp, assigned_at=stamp,
        cancelled_at=stamp, checkout_started_at=stamp, paid_at=stamp)


@pytest.mark.parametrize("offset", [None, timezone.utc, timezone(timedelta(hours=2))])
def test_queue_and_event_instants_keep_absolute_identity(offset):
    stamp = datetime(2026, 10, 25, 1, 30, tzinfo=offset)
    expected = stamp.replace(tzinfo=timezone.utc) if offset is None else stamp
    value = dto(stamp).model_dump(mode="json")
    for field in ("arrival_time", "estimated_start_time", "assigned_at", "cancelled_at", "checkout_started_at", "paid_at"):
        actual = datetime.fromisoformat(value[field].replace("Z", "+00:00"))
        assert actual.tzinfo is not None and actual == expected
    event = QueueEventRead(id=1, institute_id="inst", ticket_id="ticket", event_type="queue.paid",
        previous_status="in_checkout", status="paid", employee_id=None, occurred_at=stamp)
    assert datetime.fromisoformat(event.model_dump(mode="json")["occurred_at"].replace("Z", "+00:00")) == expected


def test_absent_queue_milestones_remain_absent():
    value = dto(datetime(2026, 10, 6, 6)).model_copy(update={field: None for field in
        ("estimated_start_time", "assigned_at", "cancelled_at", "checkout_started_at", "paid_at")}).model_dump(mode="json")
    assert all(value[field] is None for field in ("estimated_start_time", "assigned_at", "cancelled_at", "checkout_started_at", "paid_at"))


def test_sqlite_http_arrival_and_cancellation_events_have_explicit_instants(client):
    institute, _, services = _bootstrap_reference_data(client)
    headers = _auth_headers(institute_id=institute)
    before = utcnow()
    created = client.post("/api/v1/tickets", headers=headers, json={"institute_id": institute, "service_id": services[0]["id"]})
    assert created.status_code == 200
    ticket = created.json()
    instant = datetime.fromisoformat(ticket["arrival_time"].replace("Z", "+00:00"))
    assert before <= instant <= utcnow()
    cancelled = client.patch(f"/api/v1/tickets/{ticket['id']}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert datetime.fromisoformat(cancelled.json()["cancelled_at"].replace("Z", "+00:00")) >= instant
    events = client.get(f"/api/v1/tickets/{ticket['id']}/events", headers=headers).json()
    assert events and all(datetime.fromisoformat(row["occurred_at"].replace("Z", "+00:00")).tzinfo is not None for row in events)


def test_postgres_queue_and_event_reads_preserve_stored_aware_instants(postgres_flow):
    engine, institute, employee, service = postgres_flow
    with Session(engine) as db:
        ticket = create_queue_ticket(db, TicketCreate(institute_id=institute, service_id=service))
        read = _read_ticket(db, ticket).model_dump(mode="json")
        assert datetime.fromisoformat(read["arrival_time"].replace("Z", "+00:00")) == ticket.arrival_time
        event = db.scalar(select(QueueEvent).where(QueueEvent.ticket_id == ticket.id))
        assert datetime.fromisoformat(QueueEventRead.model_validate(event).model_dump(mode="json")["occurred_at"].replace("Z", "+00:00")) == event.occurred_at
