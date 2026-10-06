import pytest
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.payments.models import PaymentIntent
from app.modules.payments.intents import persist_intent
from app.modules.payments.provider import OperationKind, PaymentAmount
from app.modules.payments.outcomes import record_authorization_outcome
from test_payment_intents_9c import request
from test_payment_outcomes_9f import prepare, result
from test_ticket_workflow import _bootstrap_reference_data
from test_postgres_scheduling_4d import postgres_flow, race


@pytest.mark.parametrize("kind", [OperationKind.CAPTURE, OperationKind.CANCEL])
def test_parent_proof_full_value_and_single_reservation(client, kind):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, identifier = prepare(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    intent = request(institute, ticket, idempotency_key="child")
    with Session(main_module.engine) as db, pytest.raises(HTTPException):
        persist_intent(db, intent, kind, "provider", "account", "reference")
    with Session(main_module.engine) as db:
        record_authorization_outcome(db, institute, identifier, "provider", "account", result("authorized"))
    for value, provider, account, reference in (
        (request(institute, ticket, idempotency_key="partial", value=PaymentAmount(Decimal("1"), "CHF")), "provider", "account", "reference"),
        (intent, "other", "account", "reference"), (intent, "provider", "other", "reference"),
        (intent, "provider", "account", "unknown"),
    ):
        with Session(main_module.engine) as db, pytest.raises(HTTPException):
            persist_intent(db, value, kind, provider, account, reference)
    with Session(main_module.engine) as db:
        row = persist_intent(db, intent, kind, "provider", "account", "reference")
        assert persist_intent(db, intent, kind, "provider", "account", "reference").id == row.id
    for other in (OperationKind.CAPTURE, OperationKind.CANCEL):
        with Session(main_module.engine) as db, pytest.raises(HTTPException):
            persist_intent(db, request(institute, ticket, idempotency_key="competing"), other, "provider", "account", "reference")
    with Session(main_module.engine) as db, pytest.raises(HTTPException, match="capture confirme"):
        persist_intent(db, request(institute, ticket, idempotency_key="refund"), OperationKind.REFUND, "provider", "account", "reference")


def test_capture_and_cancel_reservations_serialize(postgres_flow):
    engine, institute, employee, care = postgres_flow
    ticket, identifier = prepare(engine, institute, employee, care)
    with Session(engine) as db:
        record_authorization_outcome(db, institute, identifier, "provider", "account", result("authorized"))
    actions = [lambda db, kind=kind: persist_intent(db, request(institute, ticket, idempotency_key=kind.value), kind, "provider", "account", "reference") for kind in (OperationKind.CAPTURE, OperationKind.CANCEL)]
    results = race(engine, actions)
    assert sum(row[0] == "ok" for row in results) == 1
    with Session(engine) as db:
        children = list(db.scalars(select(PaymentIntent).where(PaymentIntent.kind != "authorize")))
        assert len(children) == 1


@pytest.mark.parametrize("status", ["pending", "failed"])
def test_non_authorized_provider_observation_cannot_fund_capture(client, status):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, identifier = prepare(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    with Session(main_module.engine) as db:
        record_authorization_outcome(db, institute, identifier, "provider", "account", result(status))
    with Session(main_module.engine) as db, pytest.raises(HTTPException):
        persist_intent(db, request(institute, ticket, idempotency_key="capture"), OperationKind.CAPTURE, "provider", "account", "reference")


def test_same_account_authorization_cannot_be_used_for_another_ticket(client):
    from app.modules.tickets.service import create_queue_ticket
    from app.modules.tickets.schemas import TicketCreate
    institute, employees, services = _bootstrap_reference_data(client)
    _, identifier = prepare(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    with Session(main_module.engine) as db:
        record_authorization_outcome(db, institute, identifier, "provider", "account", result("authorized"))
        other = create_queue_ticket(db, TicketCreate(institute_id=institute, service_id=services[0]["id"]))
        with pytest.raises(HTTPException, match="Autorisation parente"):
            persist_intent(db, request(institute, other.id, idempotency_key="other-ticket"), OperationKind.CAPTURE, "provider", "account", "reference")
