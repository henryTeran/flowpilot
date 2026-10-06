import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.payments.executions import seal_authorization
from app.modules.payments.intents import persist_intent
from app.modules.payments.models import PaymentExecution
from app.modules.payments.provider import OperationKind
from app.modules.tickets.models import QueueEvent
from app.modules.tickets.service import start_checkout, complete_payment
from test_loyalty_earning_8r import setup
from test_payment_intents_9c import request
from test_ticket_workflow import _bootstrap_reference_data


def test_same_cashier_reopens_protected_checkout_without_mutation(client):
    institute, employees, services = _bootstrap_reference_data(client)
    employee = employees[0]["id"]
    ticket, _, _ = setup(main_module.engine, institute, employee, services[0]["id"])
    with Session(main_module.engine) as db:
        opened = start_checkout(db, ticket, employee)
        original_time, original_total = opened.checkout_started_at, opened.total_amount
        intent = persist_intent(db, request(institute, ticket), OperationKind.AUTHORIZE, "provider", "account")
        seal_authorization(db, institute, intent.id)
        events = list(db.scalars(select(QueueEvent.id)))
        replay = start_checkout(db, ticket, employee)
        assert replay.status == "in_checkout"
        assert replay.checkout_employee_id == employee
        assert (replay.checkout_started_at, replay.total_amount) == (original_time, original_total)
        assert list(db.scalars(select(QueueEvent.id))) == events
        assert db.get(PaymentExecution, intent.id).released_at is None
        with pytest.raises(HTTPException):
            start_checkout(db, ticket, employees[1]["id"])
        with pytest.raises(HTTPException):
            complete_payment(db, ticket, employee, "especes")


def test_protection_still_blocks_starting_a_new_checkout(client):
    institute, employees, services = _bootstrap_reference_data(client)
    employee = employees[0]["id"]
    ticket, _, _ = setup(main_module.engine, institute, employee, services[0]["id"])
    with Session(main_module.engine) as db:
        intent = persist_intent(db, request(institute, ticket), OperationKind.AUTHORIZE, "provider", "account")
        seal_authorization(db, institute, intent.id)
        with pytest.raises(HTTPException):
            start_checkout(db, ticket, employee)
