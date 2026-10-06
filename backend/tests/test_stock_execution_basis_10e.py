from datetime import timedelta
import pytest
from sqlalchemy import select, event
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import app.main as main_module
from app.modules.inventory.models import StockServiceBasis, StockRecipe
from app.modules.inventory import recipes, service, bases
from app.modules.inventory.schemas import ItemCreate, RecipeCreate
from app.modules.planning.service import start_service_session
from app.modules.planning.models import ServiceSession
from app.modules.appointments.models import Appointment
from app.modules.appointments.service import start_appointment, complete_appointment
from app.modules.tickets.models import TicketLine, QueueTicket
from app.modules.employees.models import Employee
from app.modules.institutes.models import Institute
from app.shared.time import utcnow
from test_inventory_10a import item
from test_stock_recipes_10c import payload
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow, race, tickets


def test_multiline_start_pins_original_recipes_quantity_and_absent_configuration(client):
    institute, employees, services = _bootstrap_reference_data(client)
    manager, operator = _auth_headers("responsable_institut", institute), _auth_headers(institute_id=institute)
    base = f"/api/v1/inventory/institutes/{institute}"
    stock = client.post(base + "/items", headers=manager, json=item()).json()
    recipe_path = base + f"/services/{services[0]['id']}/recipes"
    original = client.post(recipe_path, headers=manager, json=payload(stock["id"])).json()
    ticket = client.post("/api/v1/tickets", headers=operator,
        json=dict(institute_id=institute, service_ids=[services[0]["id"], services[1]["id"]])).json()
    with Session(main_module.engine) as db:
        first = db.scalar(select(TicketLine).where(TicketLine.ticket_id == ticket["id"], TicketLine.service_id == services[0]["id"]))
        first.quantity = 2
        db.commit()
    request = dict(ticket_id=ticket["id"], employee_id=employees[0]["id"], service_id=services[0]["id"])
    started = client.post("/api/v1/planning/sessions/start", headers=operator, json=request)
    assert started.status_code == 200
    session_id = started.json()["id"]
    path = base + f"/executions/sessions/{session_id}/basis"
    saved = client.get(path, headers=operator).json()
    assert saved["captured"] is True and len(saved["entries"]) == 2
    rows = {row["service_id"]: row for row in saved["entries"]}
    configured = rows[services[0]["id"]]
    assert configured["quantity"] == 2 and configured["recipe"] == original
    assert configured["actor_id"] == "test-user" and configured["captured_at"].endswith("Z")
    assert rows[services[1]["id"]]["state"] == "unconfigured"
    assert rows[services[1]["id"]]["recipe"] is None
    assert client.post(recipe_path, headers=manager, json=payload(stock["id"], base_revision=1,
        enabled=False, entries=[], idempotency_key="disable-after-start")).status_code == 200
    assert client.post("/api/v1/planning/sessions/start", headers=operator, json=request).json()["id"] == session_id
    assert client.get(path, headers=operator).json() == saved
    assert client.patch(f"/api/v1/planning/sessions/{session_id}/finish", headers=operator).status_code == 200
    assert client.get(path, headers=operator).json() == saved
    assert client.get(base + f"/items/{stock['id']}", headers=operator).json()["on_hand"] == "0.000"
    assert client.get(path, headers={}).status_code == 403
    assert client.get(path, headers=_auth_headers(institute_id="foreign")).status_code == 403
    assert client.get("/api/v1/inventory/institutes/foreign" + f"/executions/sessions/{session_id}/basis",
        headers=_auth_headers(institute_id="foreign")).status_code == 404
    assert client.get(base + "/executions/sessions/missing/basis", headers=operator).status_code == 404


def test_booking_basis_survives_disable_and_legacy_completion_is_not_backfilled(client):
    institute, employees, services = _bootstrap_reference_data(client)
    now = utcnow()
    with Session(main_module.engine) as db:
        stock = service.create_item(db, institute, ItemCreate(**item()), "manager")
        original = recipes.create(db, institute, services[0]["id"], RecipeCreate(**payload(stock.id,
            enabled=False, entries=[])), "manager")
        db.add(Appointment(id="basis-booking", institute_id=institute, employee_id=employees[0]["id"],
            service_id=services[0]["id"], customer_name="Basis customer", start_time=now,
            end_time=now + timedelta(minutes=15), status="arrived"))
        db.commit()
        start_appointment(db, "basis-booking", "operator")
        saved = bases.read(db, institute, "appointments", "basis-booking")
        assert saved["entries"][0]["state"] == "disabled"
        assert saved["entries"][0]["recipe"].id == original.id
        recipes.create(db, institute, services[0]["id"], RecipeCreate(**payload(stock.id,
            base_revision=1, idempotency_key="enable-later")), "manager")
        complete_appointment(db, "basis-booking", "operator")
        assert bases.read(db, institute, "appointments", "basis-booking") == saved
        db.add(Appointment(id="legacy-booking", institute_id=institute, employee_id=employees[0]["id"],
            service_id=services[0]["id"], customer_name="Legacy customer", start_time=now,
            end_time=now + timedelta(minutes=15), status="arrived"))
        db.commit()
        complete_appointment(db, "legacy-booking", "operator")
        assert bases.read(db, institute, "appointments", "legacy-booking")["captured"] is False
        assert len(list(db.scalars(select(StockServiceBasis)))) == 1


def test_start_rolls_back_every_basis_and_execution_when_capture_flush_fails(client):
    institute, employees, services = _bootstrap_reference_data(client)
    operator = _auth_headers(institute_id=institute)
    ticket = client.post("/api/v1/tickets", headers=operator,
        json=dict(institute_id=institute, service_ids=[services[0]["id"], services[1]["id"]])).json()
    def fail(db, context, instances):
        if any(isinstance(row, StockServiceBasis) for row in db.new):
            raise RuntimeError("Injected basis flush failure")
    event.listen(Session, "before_flush", fail)
    try:
        with Session(main_module.engine) as db:
            with pytest.raises(RuntimeError, match="Injected basis"):
                start_service_session(db, ticket["id"], employees[0]["id"], actor_id="operator")
            db.rollback()
    finally:
        event.remove(Session, "before_flush", fail)
    with Session(main_module.engine) as db:
        assert not list(db.scalars(select(StockServiceBasis)))
        assert not list(db.scalars(select(ServiceSession)))
        assert db.get(QueueTicket, ticket["id"]).status == "waiting"
        assert db.get(Employee, employees[0]["id"]).status == "available"
        assert all(row.performed_by_employee_id is None for row in db.scalars(select(TicketLine).where(TicketLine.ticket_id == ticket["id"])))


def test_postgres_same_start_pins_once_and_rejects_foreign_source(postgres_flow):
    engine, institute, employee, service_id = postgres_flow
    ticket = tickets(postgres_flow, count=1)[0]
    results = race(engine, [lambda db: start_service_session(db, ticket, employee, actor_id="operator"),
                            lambda db: start_service_session(db, ticket, employee, actor_id="operator")])
    assert all(status == "ok" for status, _ in results) and results[0][1] == results[1][1]
    with Session(engine) as db:
        row = db.scalar(select(StockServiceBasis))
        assert row is not None and len(list(db.scalars(select(StockServiceBasis)))) == 1
        owner = db.get(Institute, institute)
        db.add(Institute(id="basis-foreign", region_id=owner.region_id, name="Other", city="Other", timezone=owner.timezone, status="active"))
        db.commit()
        from app.modules.tickets.service import create_queue_ticket
        from app.modules.tickets.schemas import TicketCreate
        other_ticket = create_queue_ticket(db, TicketCreate(institute_id=institute, service_id=service_id))
        other_line = db.scalar(select(TicketLine.id).where(TicketLine.ticket_id == other_ticket.id))
        db.add(StockServiceBasis(id="foreign-basis", institute_id="basis-foreign", session_id=row.session_id,
            ticket_line_id=other_line, service_id=service_id, quantity=1, state="unconfigured", captured_at=utcnow()))
        with pytest.raises(IntegrityError, match="fk_stock_basis_session_owner"):
            db.commit()
        db.rollback()
        assert len(list(db.scalars(select(StockServiceBasis)))) == 1
