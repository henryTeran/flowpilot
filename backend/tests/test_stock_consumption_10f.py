import pytest
from sqlalchemy import select, event
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import app.main as main_module
from app.core.security import create_access_token
from app.modules.inventory import service, recipes, consumptions
from app.modules.inventory.models import StockConsumption, StockMovement, StockServiceBasis
from app.modules.inventory.schemas import ItemCreate, MovementCreate, RecipeCreate, ConsumptionCreate
from app.modules.planning.service import start_service_session, finish_service_session
from app.modules.planning.models import ServiceSession
from app.modules.tickets.service import create_queue_ticket
from app.modules.tickets.schemas import TicketCreate
from app.modules.tickets.models import TicketLine
from app.modules.institutes.models import Institute
from app.shared.time import utcnow
from test_inventory_10a import item, movement
from test_stock_recipes_10c import payload
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow, race


def confirmation(entries, **changes):
    return dict(entries=entries, reason="Quantites constatees en cabine", idempotency_key="actual-original", **changes)


def setup(db, institute, employee, service_id, *, configured=True, quantity=1, second_stock=2):
    first = service.create_item(db, institute, ItemCreate(**item()), "manager")
    second = service.create_item(db, institute, ItemCreate(**item(sku="CARTRIDGE", name="Cartridge",
        unit="unit", reorder_threshold="1", idempotency_key="second-item")), "manager")
    service.move(db, institute, first.id, MovementCreate(**movement()), "manager")
    if second_stock:
        service.move(db, institute, second.id, MovementCreate(**movement(quantity=str(second_stock), idempotency_key="unit-delivery")), "manager")
    if configured:
        recipes.create(db, institute, service_id, RecipeCreate(**payload(first.id,
            entries=[dict(item_id=first.id, quantity="4.125"), dict(item_id=second.id, quantity="1")])), "manager")
    ticket = create_queue_ticket(db, TicketCreate(institute_id=institute, service_id=service_id))
    line = db.scalar(select(TicketLine).where(TicketLine.ticket_id == ticket.id))
    line.quantity = quantity
    db.commit()
    execution = start_service_session(db, ticket.id, employee, actor_id="operator")
    basis = db.scalar(select(StockServiceBasis).where(StockServiceBasis.session_id == execution.id))
    return first.id, second.id, execution.id, basis.id


def test_actual_consumption_pins_original_norm_and_replays_after_stock_is_depleted(client):
    institute, employees, services = _bootstrap_reference_data(client)
    with Session(main_module.engine) as db:
        first, second, execution, basis = setup(db, institute, employees[0]["id"], services[0]["id"], quantity=2)
    manager, operator = _auth_headers("responsable_institut", institute), _auth_headers(institute_id=institute)
    base = f"/api/v1/inventory/institutes/{institute}"
    path = base + f"/bases/{basis}/consumption"
    terms = confirmation([dict(item_id=first, quantity="8.25"), dict(item_id=second, quantity="2")])
    assert client.get(path, headers=operator).json() is None
    assert client.post(path, headers=manager, json=terms).status_code == 400
    assert client.patch(f"/api/v1/planning/sessions/{execution}/finish", headers=operator).status_code == 200
    changed = payload(first, base_revision=1, idempotency_key="new-recipe", entries=[dict(item_id=first, quantity="9")])
    assert client.post(base + f"/services/{services[0]['id']}/recipes", headers=manager, json=changed).status_code == 200
    created = client.post(path, headers=manager, json=terms)
    assert created.status_code == 200
    original = created.json()
    assert original["actor_id"] == "test-user" and original["basis_id"] == basis
    assert original["matches_norm"] is True
    expected = {row["item_id"]: (row["quantity"], row["unit"]) for row in original["expected_entries"]}
    assert expected == {first: ("8.250", "ml"), second: ("2.000", "unit")}
    assert client.get(base + f"/items/{first}", headers=operator).json()["on_hand"] == "1.875"
    assert client.get(base + f"/items/{second}", headers=operator).json()["on_hand"] == "0.000"
    assert client.get(path, headers=operator).json() == original
    assert client.get(base + f"/consumptions/{original['id']}", headers=operator).json() == original
    assert client.post(path, headers=manager, json={**terms, "entries": list(reversed(terms["entries"]))}).json() == original
    history = client.get(base + f"/items/{first}/movements", headers=operator).json()
    consume = next(row for row in history if row["kind"] == "consumption")
    assert consume["consumption_id"] == original["id"] and consume["quantity"] == "-8.250"
    assert consume["id"] == next(row for row in original["entries"] if row["item_id"] == first)["movement_id"]
    for changes in (dict(reason="Changed reason"), dict(entries=[]), dict(idempotency_key="another-key")):
        assert client.post(path, headers=manager, json={**terms, **changes}).status_code == 400
    other = {"Authorization": "Bearer " + create_access_token(subject="different-manager", extra_claims={"role": "responsable_institut", "institute_id": institute})}
    assert client.post(path, headers=other, json=terms).status_code == 400


def test_shortage_rolls_back_all_items_without_reopening_the_completed_service(client):
    institute, employees, services = _bootstrap_reference_data(client)
    with Session(main_module.engine) as db:
        first, second, execution, basis = setup(db, institute, employees[0]["id"], services[0]["id"], second_stock=0)
        finish_service_session(db, execution)
        terms = ConsumptionCreate(**confirmation([dict(item_id=first, quantity="4.125"), dict(item_id=second, quantity="1")]))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as error:
            consumptions.create(db, institute, basis, terms, "manager")
        assert error.value.status_code == 400 and "Stock insuffisant" in error.value.detail
        db.rollback()
        assert not list(db.scalars(select(StockConsumption)))
        assert service.balance_milli(db, institute, first) == 10125
        assert service.balance_milli(db, institute, second) == 0
        assert db.get(ServiceSession, execution).status == "completed"
        service.move(db, institute, second, MovementCreate(**movement(quantity="1", idempotency_key="replenish")), "manager")
        confirmed = consumptions.create(db, institute, basis, terms, "manager")
        assert confirmed.matches_norm is True
        assert service.balance_milli(db, institute, first) == 6000
        assert service.balance_milli(db, institute, second) == 0


def test_explicit_actual_quantities_expose_deviation_and_unconfigured_norms(client):
    institute, employees, services = _bootstrap_reference_data(client)
    with Session(main_module.engine) as db:
        first, _, execution, basis = setup(db, institute, employees[0]["id"], services[0]["id"])
        finish_service_session(db, execution)
        row = consumptions.create(db, institute, basis, ConsumptionCreate(**confirmation([])), "manager")
        assert row.matches_norm is False and row.entries == [] and len(row.expected_entries) == 2
        assert service.balance_milli(db, institute, first) == 10125
        ticket = create_queue_ticket(db, TicketCreate(institute_id=institute, service_id=services[1]["id"]))
        second_execution = start_service_session(db, ticket.id, employees[0]["id"], actor_id="operator")
        second_basis = db.scalar(select(StockServiceBasis).where(StockServiceBasis.session_id == second_execution.id))
        finish_service_session(db, second_execution.id)
        actual = consumptions.create(db, institute, second_basis.id, ConsumptionCreate(**{
            **confirmation([dict(item_id=first, quantity="2.125")]), "idempotency_key": "manual-original"}), "manager")
        assert actual.expected_entries is None and actual.matches_norm is None
        assert service.balance_milli(db, institute, first) == 8000


def test_consumption_roles_scope_whole_units_and_direct_movement_are_protected(client):
    institute, employees, services = _bootstrap_reference_data(client)
    with Session(main_module.engine) as db:
        first, second, execution, basis = setup(db, institute, employees[0]["id"], services[0]["id"])
        finish_service_session(db, execution)
    base = f"/api/v1/inventory/institutes/{institute}"
    path = base + f"/bases/{basis}/consumption"
    manager = _auth_headers("responsable_institut", institute)
    terms = confirmation([dict(item_id=second, quantity="1")])
    for headers in ({}, _auth_headers(institute_id=institute), _auth_headers("responsable_institut", None), _auth_headers("responsable_institut", "foreign")):
        assert client.post(path, headers=headers, json=terms).status_code == 403
    assert client.post(path, headers=manager, json=confirmation([dict(item_id=second, quantity="0.125")])).status_code == 400
    for entries in ([dict(item_id=first, quantity="0")], terms["entries"] * 2, [dict(item_id=first, quantity="0.0001")]):
        assert client.post(path, headers=manager, json=confirmation(entries)).status_code == 422
    assert client.post(base + f"/items/{first}/movements", headers=manager, json=movement(kind="consumption")).status_code == 422
    assert client.post(base + "/bases/missing/consumption", headers=manager, json=terms).status_code == 404
    assert client.post(path, headers=manager, json=confirmation([dict(item_id="foreign-item", quantity="1")])).status_code == 404
    original = client.post(path, headers=manager, json=terms).json()
    foreign = "/api/v1/inventory/institutes/foreign"
    assert client.get(foreign + f"/consumptions/{original['id']}", headers=_auth_headers(institute_id="foreign")).status_code == 404
    assert client.get(foreign + f"/bases/{basis}/consumption", headers=_auth_headers(institute_id="foreign")).status_code == 404
    assert client.get(base + f"/consumptions/{original['id']}", headers=_auth_headers(institute_id="foreign")).status_code == 403


def test_header_and_consumption_movements_commit_atomically(client):
    institute, employees, services = _bootstrap_reference_data(client)
    with Session(main_module.engine) as db:
        first, second, execution, basis = setup(db, institute, employees[0]["id"], services[0]["id"])
        finish_service_session(db, execution)
        def fail(session, context, instances):
            if any(isinstance(row, StockMovement) and row.kind == "consumption" for row in session.new):
                raise RuntimeError("Injected consumption flush failure")
        event.listen(Session, "before_flush", fail)
        try:
            with pytest.raises(RuntimeError, match="Injected consumption"):
                consumptions.create(db, institute, basis, ConsumptionCreate(**confirmation([
                    dict(item_id=first, quantity="4.125"), dict(item_id=second, quantity="1")])), "manager")
            db.rollback()
        finally:
            event.remove(Session, "before_flush", fail)
        assert not list(db.scalars(select(StockConsumption)))
        assert not list(db.scalars(select(StockMovement).where(StockMovement.kind == "consumption")))
        assert service.balance_milli(db, institute, first) == 10125
        assert service.balance_milli(db, institute, second) == 2000
        assert db.get(ServiceSession, execution).status == "completed"


def test_postgres_duplicate_and_competing_confirmations(postgres_flow):
    engine, institute, employee, service_id = postgres_flow
    with Session(engine) as db:
        first, _, execution, basis = setup(db, institute, employee, service_id, configured=False)
        finish_service_session(db, execution)
    terms = ConsumptionCreate(**confirmation([dict(item_id=first, quantity="8.25")]))
    results = race(engine, [lambda db: consumptions.create(db, institute, basis, terms, "manager"),
                            lambda db: consumptions.create(db, institute, basis, terms, "manager")])
    assert results[0] == results[1] and results[0][0] == "ok"
    with Session(engine) as db:
        assert len(list(db.scalars(select(StockConsumption)))) == 1
        assert len(list(db.scalars(select(StockMovement).where(StockMovement.kind == "consumption")))) == 1
        assert service.balance_milli(db, institute, first) == 1875
        original = consumptions.create(db, institute, basis, terms, "manager")
        assert original.id == results[0][1]
        ticket = create_queue_ticket(db, TicketCreate(institute_id=institute, service_id=service_id))
        next_execution = start_service_session(db, ticket.id, employee, actor_id="operator")
        next_basis = db.scalar(select(StockServiceBasis).where(StockServiceBasis.session_id == next_execution.id)).id
        finish_service_session(db, next_execution.id)
    left = ConsumptionCreate(entries=[], reason="No material consumed", idempotency_key="first-empty")
    right = ConsumptionCreate(entries=[], reason="No material consumed", idempotency_key="second-empty")
    results = race(engine, [lambda db: consumptions.create(db, institute, next_basis, left, "manager"),
                            lambda db: consumptions.create(db, institute, next_basis, right, "manager")])
    assert sorted(status for status, _ in results) == ["conflict", "ok"]


def test_postgres_consumption_and_adjustment_share_the_stock_budget(postgres_flow):
    engine, institute, employee, service_id = postgres_flow
    with Session(engine) as db:
        first, _, execution, basis = setup(db, institute, employee, service_id, configured=False)
        finish_service_session(db, execution)
    terms = ConsumptionCreate(**confirmation([dict(item_id=first, quantity="8.25")]))
    adjustment = MovementCreate(**movement(kind="adjustment", quantity="-4", idempotency_key="concurrent-adjust"))
    results = race(engine, [lambda db: consumptions.create(db, institute, basis, terms, "manager"),
                            lambda db: service.move(db, institute, first, adjustment, "manager")])
    assert sorted(status for status, _ in results) == ["conflict", "ok"]
    with Session(engine) as db:
        assert service.balance_milli(db, institute, first) in {1875, 6125}
        assert db.get(ServiceSession, execution).status == "completed"


def test_postgres_composite_basis_and_consumption_ownership(postgres_flow):
    engine, institute, employee, service_id = postgres_flow
    with Session(engine) as db:
        first, _, execution, basis = setup(db, institute, employee, service_id, configured=False)
        finish_service_session(db, execution)
        owner = db.get(Institute, institute)
        db.add(Institute(id="foreign-consumption", region_id=owner.region_id, name="Other", city="Other", timezone=owner.timezone, status="active"))
        db.commit()
        db.add(StockConsumption(id="foreign-header", institute_id="foreign-consumption", basis_id=basis,
            actor_id="manager", reason="Invalid foreign basis", idempotency_key="foreign", created_at=utcnow()))
        with pytest.raises(IntegrityError, match="fk_stock_consumption_basis_owner"):
            db.commit()
        db.rollback()
        actual = consumptions.create(db, institute, basis, ConsumptionCreate(**confirmation([])), "manager")
        foreign_item = service.create_item(db, "foreign-consumption", ItemCreate(**item()), "manager")
        db.add(StockMovement(id="foreign-consumption-move", institute_id="foreign-consumption", item_id=foreign_item.id,
            kind="consumption", consumption_id=actual.id, quantity_milli=-1000, reason="Invalid foreign header",
            actor_id="manager", idempotency_key="foreign-move", occurred_at=utcnow()))
        with pytest.raises(IntegrityError, match="fk_stock_movement_consumption_owner"):
            db.commit()
        db.rollback()
        assert not list(db.scalars(select(StockMovement).where(StockMovement.kind == "consumption")))


def test_completed_appointment_consumption_uses_its_original_basis(client):
    from datetime import timedelta
    from app.modules.appointments.models import Appointment
    from app.modules.appointments.service import start_appointment, complete_appointment
    institute, employees, services = _bootstrap_reference_data(client)
    with Session(main_module.engine) as db:
        first, _, execution, _ = setup(db, institute, employees[0]["id"], services[0]["id"])
        finish_service_session(db, execution)
        now = utcnow()
        db.add(Appointment(id="actual-booking", institute_id=institute, employee_id=employees[0]["id"],
            service_id=services[0]["id"], customer_name="Actual customer", start_time=now,
            end_time=now + timedelta(minutes=15), status="arrived"))
        db.commit()
        start_appointment(db, "actual-booking", "operator")
        basis = db.scalar(select(StockServiceBasis).where(StockServiceBasis.appointment_id == "actual-booking"))
        original_recipe_id = basis.recipe_id
        recipes.create(db, institute, services[0]["id"], RecipeCreate(**payload(first,
            base_revision=1, enabled=False, entries=[], idempotency_key="disable-after-booking")), "manager")
        complete_appointment(db, "actual-booking", "operator")
        basis_id = basis.id
    manager = _auth_headers("responsable_institut", institute)
    base = f"/api/v1/inventory/institutes/{institute}"
    reply = client.post(base + f"/bases/{basis_id}/consumption", headers=manager,
        json=confirmation([dict(item_id=first, quantity="2.125")]))
    assert reply.status_code == 200
    recorded = reply.json()
    assert recorded["matches_norm"] is False and len(recorded["expected_entries"]) == 2
    assert next(row for row in recorded["expected_entries"] if row["item_id"] == first)["quantity"] == "4.125"
    assert client.get(base + f"/executions/appointments/actual-booking/basis", headers=manager).json()["entries"][0]["recipe"]["id"] == original_recipe_id
    assert client.get(base + f"/items/{first}", headers=manager).json()["on_hand"] == "8.000"
