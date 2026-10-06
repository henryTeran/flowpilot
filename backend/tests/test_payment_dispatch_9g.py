from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import select, event
from sqlalchemy.orm import Session, sessionmaker
import app.main as main_module
from app.modules.payments.dispatch import ProviderBinding, dispatch_authorization
from app.modules.payments.models import PaymentExecution, PaymentOutcome
from app.modules.payments.intents import persist_intent
from app.modules.payments.provider import OperationKind, ProviderResult, ProviderStatus, PaymentAmount
from app.modules.tickets.models import TicketLine
from app.modules.institutes.models import Institute
from test_payment_intents_9c import request
from test_loyalty_earning_8r import setup
from test_ticket_workflow import _bootstrap_reference_data
from test_postgres_scheduling_4d import postgres_flow


class Adapter:
    def __init__(self, action):
        self.action, self.requests = action, []
    def authorize(self, request):
        self.requests.append(request)
        return self.action(request)
    def capture(self, request, reference): raise NotImplementedError
    def refund(self, request, reference): raise NotImplementedError
    def cancel(self, request, reference): raise NotImplementedError
    def webhook(self, event): raise NotImplementedError


def prepare(engine, institute, employee, care):
    ticket, line, _ = setup(engine, institute, employee, care)
    original = request(institute, ticket)
    with Session(engine) as db:
        identifier = persist_intent(db, original, OperationKind.AUTHORIZE, "provider", "account").id
    return identifier, line, original


def outcome(request, status="authorized"):
    return ProviderResult("external-operation", ProviderStatus(status), request.value)


@pytest.mark.parametrize("terminal", ["authorized", "failed"])
def test_dispatch_terminal_replay_without_adapter_call(client, terminal):
    institute, employees, services = _bootstrap_reference_data(client)
    identifier, _, original = prepare(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    adapter = Adapter(lambda value: outcome(value, terminal))
    binding = ProviderBinding(institute, "provider", "account", adapter)
    sessions = sessionmaker(main_module.engine)
    first = dispatch_authorization(sessions, institute, identifier, binding)
    assert first == dispatch_authorization(sessions, institute, identifier, binding)
    assert adapter.requests == [original]
    assert "adapter" not in repr(binding)


def test_dispatch_unknown_retry_uses_original_request_and_keeps_seal(client):
    institute, employees, services = _bootstrap_reference_data(client)
    identifier, line, original = prepare(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    def timeout(value): raise TimeoutError("Unknown provider outcome")
    adapter = Adapter(timeout)
    binding = ProviderBinding(institute, "provider", "account", adapter)
    sessions = sessionmaker(main_module.engine)
    with pytest.raises(TimeoutError):
        dispatch_authorization(sessions, institute, identifier, binding)
    with Session(main_module.engine) as db:
        assert db.get(PaymentExecution, identifier).released_at is None
        assert list(db.scalars(select(PaymentOutcome))) == []
        db.get(TicketLine, line).unit_price = Decimal("99")
        db.get(TicketLine, line).total = Decimal("99")
        db.commit()
    adapter.action = lambda value: outcome(value, "pending")
    dispatch_authorization(sessions, institute, identifier, binding)
    adapter.action = outcome
    dispatch_authorization(sessions, institute, identifier, binding)
    assert adapter.requests == [original] * 3


def test_dispatch_binding_mismatch_and_failed_outcome_write(client):
    institute, employees, services = _bootstrap_reference_data(client)
    identifier, _, original = prepare(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    adapter = Adapter(outcome)
    sessions = sessionmaker(main_module.engine)
    for binding in (ProviderBinding("foreign", "provider", "account", adapter), ProviderBinding(institute, "provider", "other", adapter)):
        with pytest.raises(HTTPException):
            dispatch_authorization(sessions, institute, identifier, binding)
    assert adapter.requests == []
    binding = ProviderBinding(institute, "provider", "account", adapter)
    def fail(db, context, instances):
        if any(isinstance(row, PaymentOutcome) for row in db.new):
            raise RuntimeError("Injected result persistence failure")
    event.listen(Session, "before_flush", fail)
    try:
        with pytest.raises(RuntimeError):
            dispatch_authorization(sessions, institute, identifier, binding)
    finally:
        event.remove(Session, "before_flush", fail)
    with Session(main_module.engine) as db:
        assert db.get(PaymentExecution, identifier).released_at is None
        assert list(db.scalars(select(PaymentOutcome))) == []
    dispatch_authorization(sessions, institute, identifier, binding)
    assert adapter.requests == [original, original]


def test_network_callback_holds_no_postgres_institute_lock(postgres_flow):
    engine, institute, employee, care = postgres_flow
    identifier, _, original = prepare(engine, institute, employee, care)
    def network(value):
        with Session(engine) as db:
            assert db.get(PaymentExecution, identifier) is not None
            assert db.scalar(select(Institute.id).where(Institute.id == institute).with_for_update(nowait=True)) == institute
        return outcome(value)
    adapter = Adapter(network)
    assert dispatch_authorization(sessionmaker(engine), institute, identifier,
             ProviderBinding(institute, "provider", "account", adapter)) == outcome(original)


def test_concurrent_dispatch_reuses_provider_key_and_single_fact(postgres_flow):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    engine, institute, employee, care = postgres_flow
    identifier, _, original = prepare(engine, institute, employee, care)
    barrier = Barrier(2)
    def network(value):
        barrier.wait(timeout=10)
        return outcome(value)  # Simulates provider idempotence for one external operation.
    adapter = Adapter(network)
    binding = ProviderBinding(institute, "provider", "account", adapter)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: dispatch_authorization(sessionmaker(engine), institute, identifier, binding), range(2)))
    assert results == [outcome(original)] * 2
    assert adapter.requests == [original] * 2
    with Session(engine) as db:
        assert len(list(db.scalars(select(PaymentOutcome)))) == 1


@pytest.mark.parametrize("invalid", ["amount", "operation"])
def test_invalid_adapter_result_never_releases_or_records_fact(client, invalid):
    institute, employees, services = _bootstrap_reference_data(client)
    identifier, _, original = prepare(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    value = ProviderResult("external-operation", ProviderStatus.CAPTURED if invalid == "operation" else ProviderStatus.AUTHORIZED,
                           PaymentAmount(Decimal("11.35"), "CHF") if invalid == "amount" else original.value)
    adapter = Adapter(lambda request: value)
    with pytest.raises(ValueError):
        dispatch_authorization(sessionmaker(main_module.engine), institute, identifier,
                               ProviderBinding(institute, "provider", "account", adapter))
    with Session(main_module.engine) as db:
        assert db.get(PaymentExecution, identifier).released_at is None
        assert list(db.scalars(select(PaymentOutcome))) == []
