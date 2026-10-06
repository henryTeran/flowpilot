from datetime import timedelta
from sqlalchemy import select, event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.inventory import consumptions, worklist
from app.modules.inventory.models import StockServiceBasis
from app.modules.inventory.schemas import ConsumptionCreate
from app.modules.planning.service import finish_service_session
from app.modules.appointments.models import Appointment
from app.modules.appointments.service import start_appointment, complete_appointment
from app.shared.time import utcnow
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_stock_consumption_10f import setup, confirmation


def test_worklist_pending_confirmed_pages_roles_and_original_detail(client):
    institute, employees, services = _bootstrap_reference_data(client)
    operator = _auth_headers(institute_id=institute)
    base = f"/api/v1/inventory/institutes/{institute}"
    with Session(main_module.engine) as db:
        first, _, execution, basis = setup(db, institute, employees[0]["id"], services[0]["id"])
    assert client.get(base + "/consumption-work", headers=operator).json() == []
    active = client.get(base + f"/bases/{basis}/work", headers=operator).json()
    assert active["source_status"] == "in_progress" and active["consumption"] is None
    assert active["expected_entries"] is not None
    with Session(main_module.engine) as db:
        finish_service_session(db, execution)
        now = utcnow()
        db.add(Appointment(id="work-booking", institute_id=institute, employee_id=employees[0]["id"],
            service_id=services[0]["id"], customer_name="Private name never in worklist", start_time=now,
            end_time=now + timedelta(minutes=15), status="arrived"))
        db.commit()
        start_appointment(db, "work-booking", "operator")
        complete_appointment(db, "work-booking", "operator")
        booking_basis = db.scalar(select(StockServiceBasis).where(StockServiceBasis.appointment_id == "work-booking")).id
        db.add(Appointment(id="legacy-work-booking", institute_id=institute, employee_id=employees[0]["id"],
            service_id=services[0]["id"], customer_name="Legacy", start_time=now,
            end_time=now + timedelta(minutes=15), status="arrived"))
        db.commit()
        complete_appointment(db, "legacy-work-booking", "operator")
    pending = client.get(base + "/consumption-work?limit=1", headers=operator).json()
    later = client.get(base + "/consumption-work?limit=1&offset=1", headers=operator).json()
    assert len(pending) == len(later) == 1
    assert {row["basis_id"] for row in pending + later} == {basis, booking_basis}
    assert {row["source_kind"] for row in pending + later} == {"sessions", "appointments"}
    assert all(row["completed_at"].endswith("Z") for row in pending + later)
    assert "Private name" not in str(pending + later)
    assert all(row["employee_name"] for row in pending + later)
    assert next(row for row in pending + later if row["source_kind"] == "sessions")["ticket_number"] is not None
    assert next(row for row in pending + later if row["source_kind"] == "appointments")["ticket_number"] is None
    with Session(main_module.engine) as db:
        original = consumptions.create(db, institute, basis, ConsumptionCreate(**confirmation([
            dict(item_id=first, quantity="2.125")])), "manager")
    assert [row["basis_id"] for row in client.get(base + "/consumption-work", headers=operator).json()] == [booking_basis]
    confirmed = client.get(base + "/consumption-work?state=confirmed", headers=operator).json()
    assert len(confirmed) == 1 and confirmed[0]["consumption_id"] == original.id
    detail = client.get(base + f"/bases/{basis}/work", headers=operator).json()
    assert detail["consumption"]["id"] == original.id and detail["consumption"]["matches_norm"] is False
    assert detail["expected_entries"] == detail["consumption"]["expected_entries"]
    assert len(client.get(base + "/consumption-work?state=all", headers=operator).json()) == 2
    for query in ("limit=0", "limit=101", "offset=-1", "offset=100001", "state=unknown"):
        assert client.get(base + "/consumption-work?" + query, headers=operator).status_code == 422
    assert client.get(base + "/consumption-work", headers={}).status_code == 403
    assert client.get(base + "/consumption-work", headers=_auth_headers(institute_id="foreign")).status_code == 403
    assert client.get("/api/v1/inventory/institutes/foreign/consumption-work", headers=_auth_headers(institute_id="foreign")).json() == []
    assert client.get("/api/v1/inventory/institutes/foreign" + f"/bases/{basis}/work", headers=_auth_headers(institute_id="foreign")).status_code == 404
    assert client.get(base + "/bases/missing/work", headers=operator).status_code == 404


def test_worklist_is_one_bounded_union_without_per_row_recipe_reads(client):
    institute, employees, services = _bootstrap_reference_data(client)
    with Session(main_module.engine) as db:
        _, _, execution, _ = setup(db, institute, employees[0]["id"], services[0]["id"])
        finish_service_session(db, execution)
        queries = []
        def record(connection, cursor, statement, parameters, context, many):
            if statement.lstrip().upper().startswith("SELECT"):
                queries.append(statement)
        event.listen(main_module.engine, "before_cursor_execute", record)
        try:
            rows = worklist.list_work(db, institute, "all", 1, 0)
        finally:
            event.remove(main_module.engine, "before_cursor_execute", record)
        assert len(rows) == 1 and len(queries) == 1
        assert "UNION ALL" in queries[0] and "LIMIT" in queries[0]


from test_postgres_scheduling_4d import postgres_flow


def test_postgres_worklist_completed_union_and_scoped_detail(postgres_flow):
    engine, institute, employee, service_id = postgres_flow
    with Session(engine) as db:
        first, _, execution, basis = setup(db, institute, employee, service_id)
        assert worklist.list_work(db, institute, "pending", 20, 0) == []
        finish_service_session(db, execution)
        rows = worklist.list_work(db, institute, "pending", 20, 0)
        assert len(rows) == 1 and rows[0]["basis_id"] == basis
        actual = consumptions.create(db, institute, basis, ConsumptionCreate(**confirmation([
            dict(item_id=first, quantity="2.125")])), "manager")
        assert worklist.list_work(db, institute, "pending", 20, 0) == []
        confirmed = worklist.list_work(db, institute, "confirmed", 20, 0)
        assert len(confirmed) == 1 and confirmed[0]["consumption_id"] == actual.id
        detail = worklist.detail(db, institute, basis)
        assert detail.consumption.id == actual.id and detail.consumption.matches_norm is False
