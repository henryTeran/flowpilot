import pytest
from sqlalchemy import select, event
from sqlalchemy.orm import Session, sessionmaker
from fastapi import HTTPException
import app.main as main_module
from app.modules.payments.dispatch import ProviderBinding, dispatch_refund
from app.modules.payments.models import RefundOutcome, RefundExecution
from app.modules.payments.refunds import record_refund_outcome
from app.modules.payments.provider import ProviderResult, ProviderStatus
from app.modules.payments.checkout import apply_capture
from test_capture_checkout_9j import prepare
from test_refund_budget_9k import reserve
from test_payment_dispatch_9g import Adapter
from test_ticket_workflow import _bootstrap_reference_data
from test_postgres_scheduling_4d import postgres_flow, race


def prepared(engine, institute, employee, care):
    ticket, _, capture = prepare(engine, institute, employee, care)
    with Session(engine) as db:
        apply_capture(db, institute, capture, employee, "operator", "cb")
        identifier = reserve(db, institute, ticket, "refund", "10.35").id
    return ticket, identifier


class RefundAdapter(Adapter):
    def refund(self, request, reference):
        self.requests.append(request)
        return self.action(request, reference)


@pytest.mark.parametrize("status", ["refunded", "failed"])
def test_refund_dispatch_terminal_replay_and_budget_release(client, status, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, identifier = prepared(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    adapter = RefundAdapter(lambda request, reference: ProviderResult(reference, ProviderStatus(status), request.value))
    binding = ProviderBinding(institute, "provider", "account", adapter)
    sessions = sessionmaker(main_module.engine)
    first = dispatch_refund(sessions, institute, identifier, binding)
    assert dispatch_refund(sessions, institute, identifier, binding) == first
    assert len(adapter.requests) == 1
    with Session(main_module.engine) as db:
        assert len(list(db.scalars(select(RefundOutcome)))) == 1
        if status == "failed":
            reserve(db, institute, ticket, "new-attempt", "10.35")
        else:
            with pytest.raises(HTTPException):
                reserve(db, institute, ticket, "over-refund", "0.01")
    for other in ("pending", "failed" if status == "refunded" else "refunded"):
        with Session(main_module.engine) as db, pytest.raises(HTTPException):
            record_refund_outcome(db, institute, identifier, "provider", "account",
                                 ProviderResult("reference", ProviderStatus(other), first.value))

    assert_refund_downgrade_refused(main_module.engine, monkeypatch)

def test_timeout_and_failed_result_write_preserve_reservation(client):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, identifier = prepared(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    def timeout(request, reference): raise TimeoutError("Unknown refund")
    adapter = RefundAdapter(timeout)
    binding = ProviderBinding(institute, "provider", "account", adapter)
    sessions = sessionmaker(main_module.engine)
    with pytest.raises(TimeoutError):
        dispatch_refund(sessions, institute, identifier, binding)
    with Session(main_module.engine) as db:
        assert db.get(RefundExecution, identifier) is not None
        with pytest.raises(HTTPException):
            reserve(db, institute, ticket, "unknown-budget", "0.01")
    adapter.action = lambda request, reference: ProviderResult(reference, ProviderStatus.FAILED, request.value)
    def fail(db, context, instances):
        if any(isinstance(row, RefundOutcome) for row in db.new):
            raise RuntimeError("Injected refund outcome failure")
    event.listen(Session, "before_flush", fail)
    try:
        with pytest.raises(RuntimeError):
            dispatch_refund(sessions, institute, identifier, binding)
    finally:
        event.remove(Session, "before_flush", fail)
    with Session(main_module.engine) as db:
        assert list(db.scalars(select(RefundOutcome))) == []
        with pytest.raises(HTTPException):
            reserve(db, institute, ticket, "lost-result-budget", "0.01")
    dispatch_refund(sessions, institute, identifier, binding)
    assert adapter.requests[0] == adapter.requests[1] == adapter.requests[2]


def test_concurrent_refund_dispatch_records_one_fact(postgres_flow, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    engine, institute, employee, care = postgres_flow
    _, identifier = prepared(engine, institute, employee, care)
    barrier = Barrier(2)
    def network(request, reference):
        barrier.wait(timeout=10)
        return ProviderResult(reference, ProviderStatus.REFUNDED, request.value)
    binding = ProviderBinding(institute, "provider", "account", RefundAdapter(network))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: dispatch_refund(sessionmaker(engine), institute, identifier, binding), range(2)))
    assert results[0] == results[1]
    with Session(engine) as db:
        assert len(list(db.scalars(select(RefundOutcome)))) == 1

    assert_refund_downgrade_refused(engine, monkeypatch)


def test_refund_outcomes_validate_scope_reference_amount_and_kind(client):
    from decimal import Decimal
    from app.modules.payments.provider import PaymentAmount
    from app.modules.payments.refunds import seal_refund
    institute, employees, services = _bootstrap_reference_data(client)
    _, identifier = prepared(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    with Session(main_module.engine) as db:
        value = seal_refund(db, institute, identifier).value
    for invalid in (ProviderResult("foreign", ProviderStatus.REFUNDED, value),
                    ProviderResult("reference", ProviderStatus.REFUNDED, PaymentAmount(Decimal("1"), "CHF")),
                    ProviderResult("reference", ProviderStatus.CAPTURED, value)):
        with Session(main_module.engine) as db, pytest.raises(ValueError):
            record_refund_outcome(db, institute, identifier, "provider", "account", invalid)
    for scope, account in (("foreign", "account"), (institute, "other-account")):
        with Session(main_module.engine) as db, pytest.raises(HTTPException):
            record_refund_outcome(db, scope, identifier, "provider", account,
                                  ProviderResult("reference", ProviderStatus.REFUNDED, value))
    with Session(main_module.engine) as db:
        assert list(db.scalars(select(RefundOutcome))) == []


def assert_refund_downgrade_refused(engine, monkeypatch):
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
        command.stamp(config, "71de12698ce0")
        with pytest.raises(RuntimeError, match="cannot preserve provider facts"):
            command.downgrade(config, "60cd01587bdf")
