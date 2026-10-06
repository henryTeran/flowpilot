from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
from decimal import localcontext
import pytest
from sqlalchemy import select, func, event, text
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.inventory import observed, consumptions, bases, recipes, service as stock
from app.modules.inventory.observed_schemas import ObservedRequest
from app.modules.inventory.schemas import ConsumptionCreate, RecipeCreate, MovementCreate
from app.modules.inventory.models import StockServiceBasis, StockMovement, StockConsumption
from app.modules.planning.models import ServiceSession
from app.modules.planning.service import finish_service_session
from app.modules.appointments.models import Appointment
from app.modules.institutes.models import Institute
from app.modules.tickets.models import TicketLine
from test_stock_consumption_10f import setup, confirmation
from test_stock_recipes_10c import payload as recipe_terms
from test_inventory_planned_10q import NOW, appointment
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow


@pytest.fixture(autouse=True)
def stable_confirmation_clock(monkeypatch):
    monkeypatch.setattr(observed, "utcnow", lambda: NOW)
    monkeypatch.setattr(consumptions, "utcnow", lambda: NOW)


def request():
    return dict(starts_at=(NOW-timedelta(hours=12)).isoformat(),
        ends_at=(NOW+timedelta(hours=12)).isoformat(),
        observed_starts_at=(NOW-timedelta(days=1)).isoformat(), observed_ends_at=NOW.isoformat())


def finish(db, execution, ended=None):
    finish_service_session(db, execution)
    db.get(ServiceSession, execution).real_end_time = ended or NOW-timedelta(hours=1)
    db.commit()


def article(result, item_id):
    return next(row for row in result["items"] if row["item_id"] == item_id)


def test_http_observed_uses_completion_not_late_confirmation_and_never_current_norm(client, monkeypatch):
    monkeypatch.setattr(observed, "utcnow", lambda: NOW)
    institute, employees, services = _bootstrap_reference_data(client)
    employee, service = employees[0]["id"], services[0]["id"]
    with Session(main_module.engine) as db:
        serum, cartridge, execution, basis = setup(db, institute, employee, service)
        finish(db, execution)
        signed = consumptions.create(db, institute, basis, ConsumptionCreate(**confirmation([
            dict(item_id=serum, quantity="4.125"), dict(item_id=cartridge, quantity="1")])), "manager")
        # Later confirmation is at the excluded observed upper boundary.
        db.get(StockConsumption, signed.id).created_at = NOW
        for move in db.scalars(select(StockMovement).where(StockMovement.consumption_id == signed.id)):
            move.occurred_at = NOW
        recipes.create(db, institute, service, RecipeCreate(**recipe_terms(serum, base_revision=1,
            entries=[dict(item_id=serum, quantity="9")], idempotency_key="later-norm")), "manager")
        invoice_line = db.get(TicketLine, db.get(StockServiceBasis, basis).ticket_line_id)
        invoice_line.invoice_removed_at = NOW
        invoice_line.invoice_removed_by_actor = "manager"
        invoice_line.invoice_removal_reason = "not_performed"
        db.add(Institute(id="foreign", region_id=db.get(Institute, institute).region_id,
            city="Foreign", name="Foreign", timezone="UTC"))
        db.flush()
        appointment(db, "foreign", employee, service, "foreign-undated", status="completed")
        db.commit()
        movement_count = db.scalar(select(func.count()).select_from(StockMovement))
    base = f"/api/v1/inventory/institutes/{institute}/observed-projection"
    headers = _auth_headers(institute_id=institute)
    reply = client.post(base, headers=headers, json=request())
    assert reply.status_code == 200, reply.text
    result = reply.json()
    assert result["coverage"] == "complete_signed_sample"
    assert result["completed_executions"] == result["captured_bases"] == result["signed_confirmations"] == 1
    assert result["pending_bases"] == result["legacy_completed_executions"] == result["undated_completed_executions"] == 0
    assert result["assumption"] == "constant_elapsed_time_pace"
    assert result["effective_starts_at"] == "2026-10-07T10:00:00Z"
    serum_row = article(result, serum)
    assert serum_row["observed_quantity"] == "4.125"
    assert serum_row["recorded_pace_projection"] == serum_row["complete_pace_projection"] == "2.063"
    assert serum_row["on_hand"] == "6.000" and serum_row["recorded_projection_shortfall"] == "0.188"
    assert article(result, cartridge)["complete_pace_projection"] == "1.000"
    assert client.post(base+"?limit=1&offset=1", headers=headers, json=request()).json()["items"] == result["items"][1:2]
    with Session(main_module.engine) as db:
        assert db.scalar(select(func.count()).select_from(StockMovement)) == movement_count
        # Exact upper boundary excludes the execution, despite its signed quantities.
        db.get(ServiceSession, execution).real_end_time = NOW
        db.commit()
    empty = client.post(base, headers=headers, json=request()).json()
    assert empty["coverage"] == "no_completed_sample" and empty["signed_confirmations"] == 0
    assert article(empty, serum)["observed_quantity"] == "0.000"
    assert article(empty, serum)["complete_pace_projection"] is None
    for invalid in (request() | {"observed_starts_at": "2026-10-06T10:00:00"},
                    request() | {"include_waiting_queue": True}):
        assert client.post(base, headers=headers, json=invalid).status_code == 422
    assert client.post(base, headers=headers, json=request() | {"observed_ends_at": (NOW+timedelta(hours=1)).isoformat()}).status_code == 400
    assert client.post(base, headers=headers, json=request() | {"ends_at": NOW.isoformat()}).status_code == 400
    assert client.post(base, json=request()).status_code == 403
    assert client.post(base, headers=_auth_headers("collaboratrice", institute), json=request()).status_code == 403
    assert client.post(base, headers=_auth_headers(institute_id="foreign"), json=request()).status_code == 403


def test_signed_empty_pending_legacy_undated_and_appointment_sources_are_distinct(client, monkeypatch):
    monkeypatch.setattr(observed, "utcnow", lambda: NOW)
    institute, employees, services = _bootstrap_reference_data(client)
    employee, service = employees[0]["id"], services[0]["id"]
    with Session(main_module.engine) as db:
        serum, _, execution, basis = setup(db, institute, employee, service, configured=False)
        finish(db, execution, NOW-timedelta(days=1))  # Included exact lower boundary.
        partial = observed.read(db, institute, ObservedRequest(**request()), 50, 0)
        assert partial.coverage == "partial_signed_sample" and partial.pending_bases == 1
        assert all(row.complete_pace_projection is None for row in partial.items)
        consumptions.create(db, institute, basis, ConsumptionCreate(**confirmation([])), "manager")
        complete = observed.read(db, institute, ObservedRequest(**request()), 50, 0)
        assert complete.coverage == "complete_signed_sample"
        assert all(row.complete_pace_projection == "0.000" for row in complete.items)
        # A captured appointment with a signed empty measurement contributes one
        # complete source even though its current recipe is unconfigured.
        appointment(db, institute, employee, service, "observed-appointment", status="in_progress",
            actual_start_time=NOW-timedelta(hours=2))
        db.flush()
        bases.capture(db, institute, service, 1, NOW-timedelta(hours=2), "manager",
            appointment_id="observed-appointment")
        db.flush()
        appointment_basis = db.scalar(select(StockServiceBasis.id).where(
            StockServiceBasis.appointment_id == "observed-appointment"))
        row = db.get(Appointment, "observed-appointment")
        row.status = "completed"
        row.actual_end_time = NOW-timedelta(hours=1)
        db.commit()
        consumptions.create(db, institute, appointment_basis, ConsumptionCreate(**{
            **confirmation([]), "idempotency_key": "empty-appointment"}), "manager")
        result = observed.read(db, institute, ObservedRequest(**request()), 50, 0)
        assert result.completed_executions == result.captured_bases == result.signed_confirmations == 2
        assert result.coverage == "complete_signed_sample"
        appointment(db, institute, employee, service, "legacy", status="completed", actual_end_time=NOW-timedelta(hours=1))
        appointment(db, institute, employee, service, "undated", status="completed")
        appointment(db, institute, employee, service, "outside", status="completed", actual_end_time=NOW-timedelta(days=2))
        appointment(db, institute, employee, service, "cancelled", status="cancelled", actual_end_time=NOW-timedelta(hours=1))
        db.commit()
        result = observed.read(db, institute, ObservedRequest(**request()), 50, 0)
        assert result.completed_executions == 3 and result.legacy_completed_executions == 1
        assert result.undated_completed_executions == 1 and result.coverage == "partial_signed_sample"
        assert all(row.complete_pace_projection is None for row in result.items)
        assert next(row for row in result.items if row.item_id == serum).observed_quantity == "0.000"


def test_postgres_observed_query_count_and_atomic_confirmation_visibility(postgres_flow):
    engine, institute, employee, service = postgres_flow
    with Session(engine) as db:
        serum, _, execution, basis = setup(db, institute, employee, service)
        finish(db, execution)
    staged, release, reading = Event(), Event(), Event()
    reader_pid = []
    def writer():
        with Session(engine) as db:
            def hold(_db):
                staged.set()
                assert release.wait(15)
            event.listen(db, "before_commit", hold, once=True)
            return consumptions.create(db, institute, basis, ConsumptionCreate(**confirmation([
                dict(item_id=serum, quantity="4.125")])), "manager")
    def reader():
        with Session(engine) as db:
            reader_pid.append(db.scalar(text("select pg_backend_pid()")))
            reading.set()
            return observed.read(db, institute, ObservedRequest(**request()), 50, 0)
    with ThreadPoolExecutor(max_workers=2) as pool:
        write = pool.submit(writer)
        assert staged.wait(5)
        read = pool.submit(reader)
        assert reading.wait(5)
        waiting = None
        try:
            deadline = time.monotonic()+5
            with Session(engine) as observer:
                while time.monotonic() < deadline:
                    waiting = observer.scalar(text("select wait_event_type from pg_stat_activity where pid=:pid"),
                        {"pid": reader_pid[0]})
                    if waiting == "Lock":
                        break
                    observer.rollback()
                    time.sleep(.01)
            assert waiting == "Lock" and not read.done()
        finally:
            release.set()
        write.result(timeout=5)
        result = read.result(timeout=5)
        row = next(row for row in result.items if row.item_id == serum)
        assert result.coverage == "complete_signed_sample"
        assert (row.on_hand, row.observed_quantity, row.complete_pace_projection) == ("6.000", "4.125", "2.063")
    queries = []
    def record(_connection, _cursor, statement, _params, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)
    with Session(engine) as db:
        event.listen(engine, "before_cursor_execute", record)
        try:
            observed.read(db, institute, ObservedRequest(**request()), 50, 0)
            first = len(queries)
            assert first == 6
            for index in range(250):
                appointment(db, institute, employee, service, f"legacy-{index}", status="completed",
                    actual_end_time=NOW-timedelta(hours=1))
            db.commit()
            queries.clear()
            report = observed.read(db, institute, ObservedRequest(**request()), 50, 0)
            assert len(queries) == first
            assert report.completed_executions == 251 and report.legacy_completed_executions == 250
            assert report.coverage == "partial_signed_sample"
            # A future-dated signature cannot establish a measurement as of now.
            signed = db.scalar(select(StockConsumption).where(StockConsumption.basis_id == basis))
            signed.created_at = NOW+timedelta(microseconds=1)
            db.commit()
            future = observed.read(db, institute, ObservedRequest(**request()), 50, 0)
            assert future.pending_bases == 1 and future.signed_confirmations == 0
            assert all(row.complete_pace_projection is None for row in future.items)
            assert next(row for row in future.items if row.item_id == serum).observed_quantity == "0.000"
        finally:
            event.remove(engine, "before_cursor_execute", record)


def test_postgres_observed_sums_historical_cycles_above_current_stock_capacity_exactly(postgres_flow):
    engine, institute, employee, service = postgres_flow
    with Session(engine) as db:
        serum, _, execution, basis = setup(db, institute, employee, service)
        finish(db, execution)
        stock.move(db, institute, serum, MovementCreate(kind="adjustment", quantity="-10.125",
            reason="Empty before measured historical cycles", idempotency_key="empty-stock"), "manager")
        stock.move(db, institute, serum, MovementCreate(kind="receipt", quantity="999999999999.999",
            reason="First measured cycle", idempotency_key="first-cycle"), "manager")
        consumptions.create(db, institute, basis, ConsumptionCreate(**confirmation([
            dict(item_id=serum, quantity="999999999999.999")])), "manager")
        stock.move(db, institute, serum, MovementCreate(kind="receipt", quantity="999999999999.999",
            reason="Second measured cycle", idempotency_key="second-cycle"), "manager")
        appointment(db, institute, employee, service, "second-cycle-execution", status="in_progress",
            actual_start_time=NOW-timedelta(hours=2))
        db.flush()
        bases.capture(db, institute, service, 1, NOW-timedelta(hours=2), "manager",
            appointment_id="second-cycle-execution")
        db.flush()
        second_basis = db.scalar(select(StockServiceBasis.id).where(
            StockServiceBasis.appointment_id == "second-cycle-execution"))
        source = db.get(Appointment, "second-cycle-execution")
        source.status = "completed"
        source.actual_end_time = NOW-timedelta(hours=1)
        db.commit()
        consumptions.create(db, institute, second_basis, ConsumptionCreate(**{
            **confirmation([dict(item_id=serum, quantity="999999999999.999")]),
            "idempotency_key": "second-measurement"}), "manager")
        with localcontext() as context:
            context.prec = 6
            report = observed.read(db, institute, ObservedRequest(**request()), 50, 0)
        row = next(row for row in report.items if row.item_id == serum)
        assert report.coverage == "complete_signed_sample" and report.completed_executions == 2
        assert row.observed_quantity == "1999999999999.998"
        assert row.complete_pace_projection == "999999999999.999"
        assert row.on_hand == "0.000" and row.recorded_projection_shortfall == "1000000000004.124"


def test_multiline_execution_requires_every_original_confirmation_without_duplicate_source_count(client):
    institute, employees, services = _bootstrap_reference_data(client)
    from test_purchase_orders_10l import setup as catalogue
    with Session(main_module.engine) as db:
        catalogue(db, institute)
    headers = _auth_headers(institute_id=institute)
    ticket = client.post("/api/v1/tickets", headers=headers, json=dict(institute_id=institute,
        service_ids=[services[0]["id"], services[1]["id"]])).json()
    started = client.post("/api/v1/planning/sessions/start", headers=headers, json=dict(
        ticket_id=ticket["id"], employee_id=employees[0]["id"], service_id=services[0]["id"]))
    assert started.status_code == 200, started.text
    execution = started.json()["id"]
    with Session(main_module.engine) as db:
        finish(db, execution)
        originals = list(db.scalars(select(StockServiceBasis.id).where(StockServiceBasis.session_id == execution)))
        assert len(originals) == 2
        consumptions.create(db, institute, originals[0], ConsumptionCreate(**confirmation([])), "manager")
        partial = observed.read(db, institute, ObservedRequest(**request()), 50, 0)
        assert partial.completed_executions == 1 and partial.captured_bases == 2
        assert partial.signed_confirmations == partial.pending_bases == 1
        assert partial.coverage == "partial_signed_sample"
        consumptions.create(db, institute, originals[1], ConsumptionCreate(**{
            **confirmation([]), "idempotency_key": "second-original-line"}), "manager")
        complete = observed.read(db, institute, ObservedRequest(**request()), 50, 0)
        assert complete.completed_executions == 1 and complete.signed_confirmations == 2
        assert complete.coverage == "complete_signed_sample"
        assert all(row.complete_pace_projection == "0.000" for row in complete.items)
