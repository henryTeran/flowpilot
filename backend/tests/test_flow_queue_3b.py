from datetime import timedelta

import pytest
from sqlalchemy import func, select, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.appointments.models import Appointment
from app.modules.employees.models import Employee
from app.modules.planning.models import ServiceSession
from app.modules.services.models import Service
from app.modules.institutes.models import Institute
from app.modules.tickets.domain import validate_transition
from app.modules.tickets.models import QueueEvent, QueueTicket, TicketLine
from app.modules.tickets.schemas import TicketCreate
from app.modules.tickets.service import create_queue_ticket
from app.shared.time import utcnow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


@pytest.fixture
def flow(client):
    institute, employees, services = _bootstrap_reference_data(client)
    return institute, employees, services, _auth_headers(institute_id=institute)


def create(client, flow, **extra):
    institute, _, services, headers = flow
    response = client.post("/api/v1/tickets", headers=headers, json={
        "institute_id": institute, "service_id": services[0]["id"], **extra,
    })
    assert response.status_code == 200, response.text
    return response.json()


def patch(client, flow, ticket, action, **payload):
    return client.patch(f"/api/v1/tickets/{ticket['id']}/{action}", headers=flow[3], json=payload)


def events(client, flow, ticket):
    response = client.get(f"/api/v1/tickets/{ticket['id']}/events", headers=flow[3])
    assert response.status_code == 200
    return response.json()


def test_anonymous_arrival_and_standard_duration_snapshot(client, flow):
    ticket = create(client, flow, service_ids=[flow[2][0]["id"], flow[2][1]["id"]])
    assert ticket["customer_id"] is None and ticket["subscription_id"] is None
    assert ticket["arrival_time"] and ticket["queue_position"] == 1
    assert ticket["assignment_state"] == "unassigned"
    expected = flow[2][0]["duration_min"] + flow[2][1]["duration_min"]
    assert ticket["standard_duration_minutes"] == expected
    with Session(main_module.engine) as db:
        db.get(Service, flow[2][0]["id"]).duration_min += 10
        db.commit()
    started = client.post("/api/v1/planning/sessions/start", headers=flow[3], json={
        "ticket_id": ticket["id"], "employee_id": flow[1][0]["id"], "service_id": flow[2][0]["id"],
    })
    assert started.status_code == 200
    assert started.json()["duration_minutes"] == expected


def test_fifo_ties_and_cancellation_compact_positions(client, flow):
    tickets = [create(client, flow) for _ in range(3)]
    now = utcnow()
    with Session(main_module.engine) as db:
        for item in tickets:
            db.get(QueueTicket, item["id"]).arrival_time = now
        db.commit()
    response = client.get(f"/api/v1/tickets/waiting?institute_id={flow[0]}", headers=flow[3])
    ordered = response.json()
    assert [item["id"] for item in ordered] == sorted(item["id"] for item in tickets)
    assert [item["queue_position"] for item in ordered] == [1, 2, 3]
    first = patch(client, flow, ordered[0], "cancel")
    replay = patch(client, flow, ordered[0], "cancel")
    assert first.status_code == replay.status_code == 200
    assert first.json()["cancelled_at"] == replay.json()["cancelled_at"]
    assert first.json()["queue_position"] is None
    remaining = client.get(f"/api/v1/tickets/waiting?institute_id={flow[0]}", headers=flow[3]).json()
    assert [item["queue_position"] for item in remaining] == [1, 2]
    assert len(events(client, flow, ordered[0])) == 2
    assert create(client, flow)["ticket_number"] == "T-004"


def test_assignment_release_reservation_and_replays(client, flow):
    first, second = create(client, flow), create(client, flow)
    employee = flow[1][0]["id"]
    assigned = patch(client, flow, first, "assign", employee_id=employee)
    replay = patch(client, flow, first, "assign", employee_id=employee)
    assert assigned.status_code == replay.status_code == 200
    assert assigned.json()["assigned_at"] == replay.json()["assigned_at"]
    assert assigned.json()["assignment_state"] == "assigned"
    assert patch(client, flow, second, "assign", employee_id=employee).status_code == 400
    blocked_start = client.post("/api/v1/planning/sessions/start", headers=flow[3], json={
        "ticket_id": second["id"], "employee_id": employee, "service_id": flow[2][0]["id"],
    })
    assert blocked_start.status_code == 400
    assert patch(client, flow, first, "assign", employee_id=flow[1][1]["id"]).status_code == 400
    assert client.patch(f"/api/v1/employees/{employee}/status", headers=flow[3], json={"status": "pause"}).status_code == 400
    for _ in range(2):
        released = patch(client, flow, first, "unassign")
        assert released.status_code == 200
        assert released.json()["assigned_at"] is None
        assert released.json()["queue_position"] == 1
    assert [item["event_type"] for item in events(client, flow, first)] == [
        "queue.arrived", "queue.assigned", "queue.unassigned",
    ]
    assert patch(client, flow, second, "assign", employee_id=employee).status_code == 200
    assert patch(client, flow, second, "cancel").status_code == 200
    assert patch(client, flow, first, "assign", employee_id=employee).status_code == 200


def test_assignment_checks_imminent_appointment(client, flow):
    employee, service = flow[1][0]["id"], flow[2][0]
    with Session(main_module.engine) as db:
        db.add(Appointment(id="imminent", institute_id=flow[0], employee_id=employee,
            service_id=service["id"], customer_name="Reserved", status="confirmed",
            start_time=utcnow() + timedelta(minutes=1), end_time=utcnow() + timedelta(hours=1)))
        db.commit()
    ticket = create(client, flow)
    assert patch(client, flow, ticket, "assign", employee_id=employee).status_code == 400
    assert len(events(client, flow, ticket)) == 1


def test_creation_replay_mismatch_and_scope(client, flow):
    ticket = create(client, flow, idempotency_key="arrival-retry")
    assert create(client, flow, idempotency_key="arrival-retry")["id"] == ticket["id"]
    mismatch = client.post("/api/v1/tickets", headers=flow[3], json={
        "institute_id": flow[0], "service_id": flow[2][1]["id"], "idempotency_key": "arrival-retry",
    })
    assert mismatch.status_code == 400
    foreign_headers = _auth_headers(institute_id="foreign")
    for action, payload in [("assign", {"employee_id": flow[1][0]["id"]}), ("unassign", {}), ("cancel", {})]:
        response = client.patch(f"/api/v1/tickets/{ticket['id']}/{action}", headers=foreign_headers, json=payload)
        assert response.status_code == 403
    assert client.get(f"/api/v1/tickets/{ticket['id']}/events", headers=foreign_headers).status_code == 403
    assert len(events(client, flow, ticket)) == 1
    other = "other-institute"
    with Session(main_module.engine) as db:
        source = db.get(Institute, flow[0])
        db.add(Institute(id=other, region_id=source.region_id, name="Other", city="Other"))
        db.flush()
        db.add(Employee(id="other-employee", institute_id=other, first_name="Other", skills=[], status="available"))
        db.commit()
    other_flow = (other, flow[1], flow[2], _auth_headers(institute_id=other))
    assert create(client, other_flow, idempotency_key="arrival-retry")["id"] != ticket["id"]
    foreign_employee = client.get(f"/api/v1/employees?institute_id={other}", headers=other_flow[3]).json()[0]
    assert patch(client, flow, ticket, "assign", employee_id=foreign_employee["id"]).status_code == 400


def test_creation_transaction_rolls_back_partial_ticket(client, flow):
    def reject_line(*args):
        raise IntegrityError("forced line failure", {}, Exception("test failure"))
    event.listen(TicketLine, "before_insert", reject_line)
    try:
        with Session(main_module.engine) as db:
            with pytest.raises(IntegrityError):
                create_queue_ticket(db, TicketCreate(institute_id=flow[0], service_id=flow[2][0]["id"], idempotency_key="atomic"))
            assert db.scalar(select(func.count()).select_from(QueueTicket)) == 0
            assert db.scalar(select(func.count()).select_from(QueueEvent)) == 0
    finally:
        event.remove(TicketLine, "before_insert", reject_line)
    assert len(create(client, flow, idempotency_key="atomic")["lines"]) == 1


def test_whole_lifecycle_replay_has_single_events_and_session(client, flow):
    ticket = create(client, flow, idempotency_key="whole-flow")
    employee = flow[1][0]["id"]
    patch(client, flow, ticket, "assign", employee_id=employee)
    start = {"ticket_id": ticket["id"], "employee_id": employee, "service_id": flow[2][0]["id"]}
    first = client.post("/api/v1/planning/sessions/start", headers=flow[3], json=start)
    replay = client.post("/api/v1/planning/sessions/start", headers=flow[3], json=start)
    assert first.status_code == replay.status_code == 200
    assert first.json()["id"] == replay.json()["id"]
    assert patch(client, flow, ticket, "cancel").status_code == 400
    assert patch(client, flow, ticket, "unassign").status_code == 400
    session = first.json()["id"]
    for _ in range(2):
        assert client.patch(f"/api/v1/planning/sessions/{session}/finish", headers=flow[3]).status_code == 200
    active = client.get(f"/api/v1/tickets/waiting?institute_id={flow[0]}", headers=flow[3]).json()[0]
    assert active["queue_position"] is None and active["status"] == "ready_for_checkout"
    assert active["assignment_state"] == "completed"
    for _ in range(2):
        assert patch(client, flow, ticket, "checkout/start", employee_id=employee).status_code == 200
    # Checkout corrections cannot invalidate the original creation replay key.
    assert patch(client, flow, ticket, "checkout/lines/add", service_id=flow[2][1]["id"]).status_code == 200
    assert create(client, flow, idempotency_key="whole-flow")["id"] == ticket["id"]
    paid = patch(client, flow, ticket, "checkout/pay", employee_id=employee, payment_method="cb")
    replay = patch(client, flow, ticket, "checkout/pay", employee_id=employee, payment_method="cb")
    assert paid.status_code == replay.status_code == 200
    assert paid.json()["paid_at"] == replay.json()["paid_at"]
    assert patch(client, flow, ticket, "checkout/pay", employee_id=employee, payment_method="especes").status_code == 400
    assert patch(client, flow, ticket, "cancel").status_code == 400
    assert [item["event_type"] for item in events(client, flow, ticket)] == [
        "queue.arrived", "queue.assigned", "queue.service_started", "queue.service_finished",
        "queue.checkout_started", "queue.paid",
    ]
    with Session(main_module.engine) as db:
        assert db.scalar(select(func.count()).select_from(ServiceSession)) == 1
        assert db.get(Employee, employee).status == "available"


@pytest.mark.parametrize("status", ["pause", "absent", "offline", "busy"])
def test_operational_states_deny_assignment(client, flow, status):
    employee = flow[1][0]["id"]
    response = client.patch(f"/api/v1/employees/{employee}/status", headers=flow[3], json={"status": status})
    assert response.status_code == 200
    assert patch(client, flow, create(client, flow), "assign", employee_id=employee).status_code == 400
    assert client.patch(f"/api/v1/employees/{employee}/status", headers=flow[3], json={"status": "available"}).status_code == 200


def test_employee_creation_rejects_unknown_operational_state(client, flow):
    response = client.post("/api/v1/employees", headers=flow[3], json={
        "institute_id": flow[0], "first_name": "Test", "status": "imaginary",
    })
    assert response.status_code == 422


def test_lifecycle_policy_forbids_terminal_reentry():
    for status in ("paid", "cancelled", "completed"):
        with pytest.raises(ValueError):
            validate_transition(status, "waiting")
