from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from decimal import localcontext
from threading import Event
import time
from sqlalchemy import select, func, event, text
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.inventory import planned, recipes
from app.modules.inventory.schemas import RecipeCreate
from app.modules.inventory.planned_schemas import PlannedRequest
from app.modules.inventory.models import StockMovement, StockServiceBasis, StockRecipe
from app.modules.appointments.models import Appointment
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.institutes.models import Institute
from test_purchase_orders_10l import setup
from test_stock_recipes_10c import payload as terms
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow

NOW = datetime(2026, 10, 7, 10, tzinfo=timezone.utc)


def request(queue=True):
    return dict(starts_at=(NOW - timedelta(hours=10)).isoformat(),
        ends_at=(NOW + timedelta(hours=14)).isoformat(), include_waiting_queue=queue)


def appointment(db, institute, employee, service, key, **changes):
    db.add(Appointment(**(dict(id=key, institute_id=institute, employee_id=employee,
        service_id=service, customer_name="Private source name", status="scheduled",
        start_time=NOW + timedelta(hours=1), end_time=NOW + timedelta(hours=2)) | changes)))


def ticket(db, institute, service, key, quantity=1, **changes):
    db.add(QueueTicket(id=key, institute_id=institute, ticket_number=key,
        arrival_time=NOW, status=changes.pop("status", "waiting")))
    db.add(TicketLine(**(dict(id=key + "-line", ticket_id=key, service_id=service,
        quantity=quantity, duration_minutes=15) | changes)))


def test_planned_http_actual_sources_provisional_norms_coverage_and_no_writes(client, monkeypatch):
    monkeypatch.setattr(planned, "utcnow", lambda: NOW)
    institute, employees, services = _bootstrap_reference_data(client)
    service, other = services[0]["id"], services[1]["id"]
    employee = employees[0]["id"]
    with Session(main_module.engine) as db:
        serum, _, _ = setup(db, institute)
        original = recipes.create(db, institute, service, RecipeCreate(**terms(serum)), "manager")
        appointment(db, institute, employee, service, "planned")
        appointment(db, institute, employee, service, "arrived", status="arrived",
            start_time=NOW-timedelta(hours=1), end_time=NOW+timedelta(minutes=1))
        for status in ("cancelled", "no_show", "in_progress", "completed"):
            appointment(db, institute, employee, service, status, status=status)
        appointment(db, institute, employee, service, "upper-bound", start_time=NOW+timedelta(hours=14),
            end_time=NOW+timedelta(hours=15))
        appointment(db, institute, employee, service, "lower-bound", start_time=NOW-timedelta(hours=1), end_time=NOW)
        appointment(db, institute, employee, service, "already-started", actual_start_time=NOW)
        ticket(db, institute, service, "waiting", quantity=3)
        ticket(db, institute, service, "assigned", quantity=2, status="assigned")
        ticket(db, institute, other, "unknown-norm", quantity=2)
        for status in ("cancelled", "paid", "in_progress", "ready_for_checkout"):
            ticket(db, institute, service, "queue-"+status, status=status)
        ticket(db, institute, service, "removed", invoice_removed_at=NOW,
            invoice_removed_by_actor="manager", invoice_removal_reason="not_performed")
        ticket(db, institute, service, "performed", performed_by_employee_id=employee)
        own = db.get(Institute, institute)
        db.add(Institute(id="foreign-planned", name="Foreign", region_id=own.region_id, city="Foreign", timezone="UTC"))
        db.flush()
        appointment(db, "foreign-planned", employee, service, "foreign-appointment")
        ticket(db, "foreign-planned", service, "foreign-ticket", quantity=100)
        db.commit()
    base = f"/api/v1/inventory/institutes/{institute}"
    headers = _auth_headers(institute_id=institute)
    reply = client.post(base+"/planned-demand", headers=headers, json=request())
    assert reply.status_code == 200, reply.text
    result = reply.json()
    assert result["appointment_count"] == 2 and result["waiting_line_count"] == 3
    assert result["service_quantity"] == 9 and result["missing_norm_quantity"] == 2
    assert result["coverage"] == "partial_recorded_norms"
    assert result["effective_starts_at"] == "2026-10-07T10:00:00Z"
    assert result["norm_basis"] == "provisional_current_at_read"
    assert result["queue_timing"] == "unscheduled_at_read"
    article = next(row for row in result["items"] if row["item_id"] == serum)
    assert article["known_demand"] == "28.875" and article["complete_demand"] is None
    assert "Private source name" not in reply.text
    excluded = client.post(base+"/planned-demand", headers=headers, json=request(False)).json()
    assert excluded["waiting_line_count"] == 0 and excluded["service_quantity"] == 2
    assert excluded["coverage"] == "complete_recorded_norms"
    assert next(row for row in excluded["items"] if row["item_id"] == serum)["complete_demand"] == "8.250"
    with Session(main_module.engine) as db:
        recipes.create(db, institute, service, RecipeCreate(**terms(serum, base_revision=1,
            entries=[dict(item_id=serum, quantity="8.250")], idempotency_key="new-provisional")), "manager")
        recipes.create(db, institute, other, RecipeCreate(**terms(serum, enabled=False,
            entries=[], idempotency_key="explicit-disabled")), "manager")
    updated = client.post(base+"/planned-demand", headers=headers, json=request()).json()
    assert updated["coverage"] == "complete_recorded_norms"
    assert updated["disabled_norm_quantity"] == 2 and updated["missing_norm_quantity"] == 0
    assert next(row for row in updated["items"] if row["item_id"] == serum)["complete_demand"] == "57.750"
    assert client.post(base+"/planned-demand?limit=1&offset=1", headers=headers, json=request()).json()["items"] == updated["items"][1:2]
    with Session(main_module.engine) as db:
        assert db.scalar(select(func.count()).select_from(StockMovement)) == 0
        assert db.scalar(select(func.count()).select_from(StockServiceBasis)) == 0
        assert db.get(StockRecipe, original.id).revision == 1
    assert client.post(base+"/planned-demand", json=request()).status_code == 403
    assert client.post(base+"/planned-demand", headers=_auth_headers("collaboratrice", institute), json=request()).status_code == 403
    assert client.post(base+"/planned-demand", headers=_auth_headers(institute_id="foreign-planned"), json=request()).status_code == 403
    for invalid in (request() | {"include_waiting_queue": 1}, request() | {"starts_at": "2026-10-07T00:00:00"},
                    request() | {"quantity": 3}):
        assert client.post(base+"/planned-demand", headers=headers, json=invalid).status_code == 422
    expired = request() | {"ends_at": NOW.isoformat()}
    assert client.post(base+"/planned-demand", headers=headers, json=expired).status_code == 400


def test_postgres_exact_source_volume_and_constant_queries(postgres_flow, monkeypatch):
    monkeypatch.setattr(planned, "utcnow", lambda: NOW)
    engine, institute, employee, service = postgres_flow
    with Session(engine) as db:
        serum, _, _ = setup(db, institute)
        recipes.create(db, institute, service, RecipeCreate(**terms(serum,
            entries=[dict(item_id=serum, quantity="999999999999.999")])), "manager")
        ticket(db, institute, service, "large-queue", quantity=100000)
        db.commit()
        queries = []
        def record(_connection, _cursor, statement, _params, _context, _many):
            if statement.lstrip().upper().startswith("SELECT"):
                queries.append(statement)
        event.listen(engine, "before_cursor_execute", record)
        try:
            with localcontext() as context:
                context.prec = 6
                result = planned.read(db, institute, PlannedRequest(**request()), 50, 0)
            first_count = len(queries)
            article = next(row for row in result.items if row.item_id == serum)
            assert article.known_demand == "99999999999999900.000"
            assert article.complete_demand == article.known_demand
            assert first_count == 8
            for index in range(250):
                appointment(db, institute, employee, service, f"volume-{index}")
            db.commit()
            queries.clear()
            second = planned.read(db, institute, PlannedRequest(**request()), 50, 0)
            assert len(queries) == first_count
            assert second.service_quantity == 100250 and second.appointment_count == 250
            empty = planned.read(db, institute, PlannedRequest(**request(False)), 1, 1000)
            assert empty.items == [] and empty.service_quantity == 250
        finally:
            event.remove(engine, "before_cursor_execute", record)


def test_postgres_planned_read_waits_for_current_norm_commit(postgres_flow, monkeypatch):
    monkeypatch.setattr(planned, "utcnow", lambda: NOW)
    engine, institute, employee, service = postgres_flow
    with Session(engine) as db:
        serum, _, _ = setup(db, institute)
        recipes.create(db, institute, service, RecipeCreate(**terms(serum)), "manager")
        appointment(db, institute, employee, service, "norm-source")
        db.commit()
    staged, release, reading = Event(), Event(), Event()
    reader_pid = []
    def writer():
        with Session(engine) as db:
            def hold(_db):
                staged.set()
                assert release.wait(15)
            event.listen(db, "before_commit", hold, once=True)
            return recipes.create(db, institute, service, RecipeCreate(**terms(serum,
                base_revision=1, entries=[dict(item_id=serum, quantity="8.250")],
                idempotency_key="staged-norm")), "manager")
    def reader():
        with Session(engine) as db:
            reader_pid.append(db.scalar(text("select pg_backend_pid()")))
            reading.set()
            return planned.read(db, institute, PlannedRequest(**request(False)), 50, 0)
    with ThreadPoolExecutor(max_workers=2) as pool:
        write = pool.submit(writer)
        assert staged.wait(5)
        read = pool.submit(reader)
        assert reading.wait(5)
        waiting = None
        try:
            deadline = time.monotonic() + 5
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
        assert write.result(timeout=5).revision == 2
        result = read.result(timeout=5)
        assert next(row for row in result.items if row.item_id == serum).complete_demand == "8.250"
