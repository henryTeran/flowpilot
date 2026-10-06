import pytest
from fastapi import HTTPException
from sqlalchemy import select, event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.payments.models import ParentOperationExecution, PaymentIntent, PaymentExecution
from app.modules.payments.executions import seal_parent_operation
from app.modules.payments.intents import persist_intent
from app.modules.payments.provider import OperationKind
from app.modules.payments.outcomes import record_authorization_outcome
from app.modules.tickets.service import complete_payment
from test_payment_intents_9c import request
from test_payment_outcomes_9f import prepare, result
from test_ticket_workflow import _bootstrap_reference_data
from test_postgres_scheduling_4d import postgres_flow, race


def child(engine, institute, employee, care, kind):
    ticket, parent = prepare(engine, institute, employee, care)
    payload = request(institute, ticket, idempotency_key="child")
    with Session(engine) as db:
        record_authorization_outcome(db, institute, parent, "provider", "account", result("authorized"))
        identifier = persist_intent(db, payload, kind, "provider", "account", "reference").id
    return ticket, parent, identifier, payload


@pytest.mark.parametrize("kind", [OperationKind.CAPTURE, OperationKind.CANCEL])
def test_child_seal_replay_scope_and_parent_protection(client, kind, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    employee = employees[0]["id"]
    ticket, parent, identifier, payload = child(main_module.engine, institute, employee, services[0]["id"], kind)
    with Session(main_module.engine) as db:
        assert seal_parent_operation(db, institute, identifier) == payload
    with Session(main_module.engine) as db:
        row = db.get(ParentOperationExecution, identifier)
        assert row.parent_intent_id == parent
        assert db.get(PaymentExecution, parent).released_at is None
        assert seal_parent_operation(db, institute, identifier) == payload
        with pytest.raises(HTTPException):
            seal_parent_operation(db, "foreign", identifier)
    with Session(main_module.engine) as db, pytest.raises(HTTPException):
        complete_payment(db, ticket, employee, "cb")
    assert_downgrade_refused(main_module.engine, monkeypatch)


def test_child_seal_write_failure_does_not_unprotect_parent(client):
    institute, employees, services = _bootstrap_reference_data(client)
    _, parent, identifier, payload = child(main_module.engine, institute, employees[0]["id"], services[0]["id"], OperationKind.CAPTURE)
    def fail(db, context, instances):
        if any(isinstance(row, ParentOperationExecution) for row in db.new):
            raise RuntimeError("Injected child seal failure")
    event.listen(Session, "before_flush", fail)
    try:
        with Session(main_module.engine) as db, pytest.raises(RuntimeError):
            seal_parent_operation(db, institute, identifier)
    finally:
        event.remove(Session, "before_flush", fail)
    with Session(main_module.engine) as db:
        assert db.get(ParentOperationExecution, identifier) is None
        assert db.get(PaymentExecution, parent).released_at is None
        assert seal_parent_operation(db, institute, identifier) == payload


def test_duplicate_child_seal_serializes(postgres_flow, monkeypatch):
    engine, institute, employee, care = postgres_flow
    _, parent, identifier, payload = child(engine, institute, employee, care, OperationKind.CANCEL)
    def seal(db):
        seal_parent_operation(db, institute, identifier)
        return db.get(PaymentIntent, identifier)
    results = race(engine, [seal] * 2)
    assert all(row[0] == "ok" for row in results) and results[0][1] == results[1][1]
    with Session(engine) as db:
        assert len(list(db.scalars(select(ParentOperationExecution)))) == 1
        assert db.get(PaymentExecution, parent).released_at is None
    assert_downgrade_refused(engine, monkeypatch)


def assert_downgrade_refused(engine, monkeypatch):
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from app.core.config import settings
    from sqlalchemy import text
    url = engine.url
    if engine.dialect.name == "postgresql":
        with engine.connect() as connection:
            schema = connection.scalar(text("SELECT current_schema()"))
        assert schema.startswith("fp_test_")
        url = url.update_query_dict({"options": f"-csearch_path={schema}"})
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    with monkeypatch.context() as patch:
        patch.setattr(settings, "DATABASE_URL", url.render_as_string(hide_password=False))
        command.stamp(config, "5fbc90476acf")
        with pytest.raises(RuntimeError, match="cannot preserve dispatch seals"):
            command.downgrade(config, "4eab893659be")


@pytest.mark.parametrize("kind,status", [(OperationKind.CAPTURE, "captured"), (OperationKind.CANCEL, "cancelled"), (OperationKind.CAPTURE, "failed"), (OperationKind.CANCEL, "failed")])
def test_child_dispatch_terminal_replay_and_release(client, kind, status, monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from app.modules.payments.dispatch import ProviderBinding, dispatch_parent_operation
    from app.modules.payments.models import ParentOperationOutcome
    from app.modules.payments.provider import ProviderResult, ProviderStatus
    from test_payment_dispatch_9g import Adapter
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, parent, identifier, payload = child(main_module.engine, institute, employees[0]["id"], services[0]["id"], kind)
    calls = []
    class ChildAdapter(Adapter):
        def operation(self, request, reference):
            calls.append((request, reference))
            return ProviderResult(reference, ProviderStatus(status), request.value)
        capture = operation
        cancel = operation
    binding = ProviderBinding(institute, "provider", "account", ChildAdapter(None))
    sessions = sessionmaker(main_module.engine)
    first = dispatch_parent_operation(sessions, institute, identifier, binding)
    assert dispatch_parent_operation(sessions, institute, identifier, binding) == first
    assert calls == [(payload, "reference")]
    with Session(main_module.engine) as db:
        assert len(list(db.scalars(select(ParentOperationOutcome)))) == 1
        assert (db.get(PaymentExecution, parent).released_at is not None) == (status == "cancelled")
        if status == "failed":
            other = OperationKind.CANCEL if kind is OperationKind.CAPTURE else OperationKind.CAPTURE
            persist_intent(db, request(institute, ticket, idempotency_key="retry-other"), other, "provider", "account", "reference")

    from app.modules.payments.outcomes import record_parent_outcome
    conflicting = ("captured" if kind is OperationKind.CAPTURE else "cancelled") if status == "failed" else "failed"
    for other_status in (conflicting, "pending"):
        with Session(main_module.engine) as db, pytest.raises(HTTPException):
            record_parent_outcome(db, institute, identifier, "provider", "account",
                                  ProviderResult("reference", ProviderStatus(other_status), payload.value))
    assert_downgrade_refused(main_module.engine, monkeypatch)

def test_child_timeout_and_cancel_write_failure_keep_parent_protected(client):
    from sqlalchemy.orm import sessionmaker
    from app.modules.payments.dispatch import ProviderBinding, dispatch_parent_operation
    from app.modules.payments.models import ParentOperationOutcome
    from app.modules.payments.provider import ProviderResult, ProviderStatus
    from test_payment_dispatch_9g import Adapter
    institute, employees, services = _bootstrap_reference_data(client)
    _, parent, identifier, payload = child(main_module.engine, institute, employees[0]["id"], services[0]["id"], OperationKind.CANCEL)
    class ChildAdapter(Adapter):
        def cancel(self, request, reference):
            self.requests.append(request)
            return self.action(request, reference)
    def timeout(request, reference): raise TimeoutError("Unknown cancellation")
    adapter = ChildAdapter(timeout)
    binding = ProviderBinding(institute, "provider", "account", adapter)
    sessions = sessionmaker(main_module.engine)
    with pytest.raises(TimeoutError):
        dispatch_parent_operation(sessions, institute, identifier, binding)
    def fail(db, context, instances):
        if any(isinstance(row, ParentOperationOutcome) for row in db.new):
            raise RuntimeError("Injected cancellation fact failure")
    adapter.action = lambda value, reference: ProviderResult(reference, ProviderStatus.CANCELLED, value.value)
    event.listen(Session, "before_flush", fail)
    try:
        with pytest.raises(RuntimeError):
            dispatch_parent_operation(sessions, institute, identifier, binding)
    finally:
        event.remove(Session, "before_flush", fail)
    with Session(main_module.engine) as db:
        assert db.get(PaymentExecution, parent).released_at is None
        assert list(db.scalars(select(ParentOperationOutcome))) == []
    dispatch_parent_operation(sessions, institute, identifier, binding)
    assert adapter.requests == [payload] * 3


def test_concurrent_cancel_dispatch_records_one_fact(postgres_flow):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy.orm import sessionmaker
    from app.modules.payments.dispatch import ProviderBinding, dispatch_parent_operation
    from app.modules.payments.models import ParentOperationOutcome
    from app.modules.payments.provider import ProviderResult, ProviderStatus
    from test_payment_dispatch_9g import Adapter
    engine, institute, employee, care = postgres_flow
    _, parent, identifier, payload = child(engine, institute, employee, care, OperationKind.CANCEL)
    barrier = Barrier(2)
    class ChildAdapter(Adapter):
        def cancel(self, request, reference):
            barrier.wait(timeout=10)
            return ProviderResult(reference, ProviderStatus.CANCELLED, request.value)
    binding = ProviderBinding(institute, "provider", "account", ChildAdapter(None))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: dispatch_parent_operation(sessionmaker(engine), institute, identifier, binding), range(2)))
    assert results[0] == results[1]
    with Session(engine) as db:
        assert len(list(db.scalars(select(ParentOperationOutcome)))) == 1
        assert db.get(PaymentExecution, parent).released_at is not None
