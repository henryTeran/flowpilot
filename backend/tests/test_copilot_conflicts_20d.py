from datetime import datetime, timedelta, timezone
from itertools import permutations
from sqlalchemy import event, select
from sqlalchemy.orm import Session
import app.main as main_module
from app.database.session import get_db
from app.modules.workforce import conflicts
from app.modules.workforce.models import EmployeeAbsence, AbsenceCancellation
from app.modules.appointments.models import Appointment
from app.modules.planning.models import ServiceSession
from app.modules.tickets.schemas import TicketCreate
from app.modules.tickets.models import TicketLine
from app.modules.tickets.service import create_queue_ticket
from app.modules.institutes.models import Institute
from app.modules.employees.models import Employee
from app.modules.waitlist.originals import fingerprint
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers

FIRST = datetime(2026, 10, 9, 10, tzinfo=timezone.utc)
MESSAGE = "Examiner les conflits de planning"


def test_half_open_overlap_clipping_and_permutation():
    sources = [conflicts.Commitment(kind="appointment", id="a", start_at=FIRST, end_at=FIRST+timedelta(hours=1)),
        conflicts.Commitment(kind="session", id="b", start_at=FIRST+timedelta(minutes=30), end_at=FIRST+timedelta(minutes=90)),
        conflicts.Commitment(kind="appointment", id="adjacent", start_at=FIRST+timedelta(minutes=90), end_at=FIRST+timedelta(hours=2))]
    for permutation in permutations(sources):
        result = list(conflicts.overlaps(permutation, FIRST+timedelta(minutes=45), FIRST+timedelta(minutes=55)))
        assert len(result) == 1 and result[0].duration_us == "600000000"
        assert result[0].left.id == "a" and result[0].right.id == "b"


def exercise(client, engine, institute, employee, service):
    with Session(engine) as db:
        ticket = create_queue_ticket(db, TicketCreate(institute_id=institute, service_id=service))
        line = db.scalar(select(TicketLine).where(TicketLine.ticket_id == ticket.id))
        db.add(ServiceSession(id="planned_commitment", institute_id=institute, employee_id=employee,
            service_id=service, ticket_line_id=line.id, status="planned", duration_minutes=60,
            start_time=FIRST+timedelta(hours=6), planned_end_time=FIRST+timedelta(hours=7)))
        owner = db.get(Institute, institute)
        db.add(Institute(id="conflict_foreign", region_id=owner.region_id, name="Private", city="Other"))
        db.flush()
        db.add(Employee(id="foreign_conflict_employee", institute_id="conflict_foreign", first_name="Private", status="available", skills=[]))
        for identity, minutes, end, status in [("a", 0, 60, "confirmed"), ("b", 30, 90, "scheduled"),
                ("adjacent", 90, 120, "confirmed"), ("cancelled", 0, 120, "cancelled"), ("invalid", 50, 40, "confirmed")]:
            db.add(Appointment(id=identity, institute_id=institute, employee_id=employee, service_id=service,
                customer_name="Private client", phone="Private phone", notes="Private notes", status=status,
                start_time=FIRST+timedelta(minutes=minutes), end_time=FIRST+timedelta(minutes=end),
                booked_start_time=FIRST-timedelta(days=1), booked_end_time=FIRST-timedelta(days=1)+timedelta(minutes=30)))
        for identity in ("absence", "cancelled_absence"):
            db.add(EmployeeAbsence(id=identity, institute_id=institute, employee_id=employee, kind="absence",
                start_time=FIRST+timedelta(minutes=45), end_time=FIRST+timedelta(minutes=50), reason="Private absence",
                actor_id="manager", idempotency_key=identity, created_at=FIRST-timedelta(days=1)))
        db.flush()
        db.add(AbsenceCancellation(id="cancel_original", institute_id=institute, absence_id="cancelled_absence",
            reason="Private cancellation", actor_id="manager", idempotency_key="cancel", created_at=FIRST))
        db.commit()
    def post(ui=None, role="responsable_institut"):
        return client.post("/api/v1/copilot/query", headers=_auth_headers(role, institute),
            json={"message": MESSAGE, "ui_context": ui if ui is not None else {"employee_id": employee, "day": "2026-10-09"}})
    statements = []
    def collect(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine, "before_cursor_execute", collect)
    try:
        response = post()
        assert response.status_code == 200, response.text
        evidence = response.json()["evidence"]
        result = evidence["result"]
        assert result["source_count"] == 5 and result["invalid_source_count"] == 1
        assert result["overlap_count"] == 3 and len(result["overlaps"]) == 3
        assert not result["resource_conflicts_covered"] and not result["physical_activity_proven"]
        assert result["employee_id"] == employee and result["institute_id"] == institute
        assert evidence["fingerprint"] == fingerprint({k: v for k, v in evidence.items() if k != "fingerprint"})
        assert all(secret not in response.text for secret in ("Private", "cancelled_absence", '"cancelled"', '"booked_start_time"'))
        assert response.json()["actions"] == []
    finally:
        event.remove(engine, "before_cursor_execute", collect)
    assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP"}
    assert post(role="accueil").status_code == 403
    assert post({"day": "2026-10-09"}).json()["status"] == "clarification"
    assert post({"employee_id": "foreign_conflict_employee", "day": "2026-10-09"}).status_code == 404
    assert post({"employee_id": employee, "day": "2026-10-09", "service_id": service}).status_code == 400
    assert post({"employee_id": employee, "day": 1}).status_code == 422
    with Session(engine) as db:
        for index in range(12):
            db.add(Appointment(id=f"many_{index:02}", institute_id=institute, employee_id=employee, service_id=service,
                customer_name="Private", status="confirmed", start_time=FIRST+timedelta(hours=3), end_time=FIRST+timedelta(hours=4)))
        db.commit()
    bounded = post().json()["evidence"]["result"]
    assert bounded["overlap_count"] == 69 and len(bounded["overlaps"]) == 50


def test_sqlite_conflict_sources_and_signed_permissions(client):
    institute, employees, services = _bootstrap_reference_data(client)
    exercise(client, main_module.engine, institute, employees[0]["id"], services[0]["id"])


def test_postgres_conflict_sources_and_signed_permissions(client, postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    def database():
        with Session(engine) as db:
            yield db
    main_module.app.dependency_overrides[get_db] = database
    monkeypatch.setattr(main_module, "engine", engine)
    exercise(client, engine, institute, employee, service)
