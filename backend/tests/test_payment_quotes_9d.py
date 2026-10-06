from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.payments.intents import persist_intent, validate_prepared_authorization
from app.modules.payments.provider import OperationKind, PaymentAmount
from app.modules.gift_cards.service import issue_card
from app.modules.gift_cards.schemas import GiftCardIssue, AllocationCreate
from app.modules.gift_cards.tenders import allocate
from app.modules.tickets.models import QueueTicket, TicketLine
from test_payment_intents_9c import request
from test_loyalty_earning_8r import setup
from test_ticket_workflow import _bootstrap_reference_data


def test_authorization_uses_exact_gift_remainder_and_rechecks_first_dispatch(client):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, line, customer = setup(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    with Session(main_module.engine) as db:
        card = issue_card(db, institute, GiftCardIssue(amount="20", valid_days=30, reason="Explicit gift credit", idempotency_key="gift"), "manager")
        allocate(db, institute, card.id, AllocationCreate(ticket_id=ticket, amount="1.35", idempotency_key="funding"), "operator")
        with pytest.raises(HTTPException):
            persist_intent(db, request(institute, ticket), OperationKind.AUTHORIZE, "provider", "account")
        db.rollback()
        intent = request(institute, ticket, value=PaymentAmount(Decimal("9.00"), "CHF"))
        row = persist_intent(db, intent, OperationKind.AUTHORIZE, "provider", "account")
        identifier = row.id
        assert validate_prepared_authorization(db, institute, identifier) == intent
        db.get(TicketLine, line).unit_price = Decimal("11.35")
        db.get(TicketLine, line).total = Decimal("11.35")
        db.commit()
        assert persist_intent(db, intent, OperationKind.AUTHORIZE, "provider", "account").id == identifier
        with pytest.raises(HTTPException):
            validate_prepared_authorization(db, institute, identifier)
        db.rollback()
        with pytest.raises(HTTPException):
            validate_prepared_authorization(db, "foreign", identifier)


@pytest.mark.parametrize("state", ["paid", "cancelled", "waiting", "fullgift", "currency"])
def test_new_authorization_rejects_ineligible_or_fully_covered_ticket(client, state):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, line, customer = setup(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    with Session(main_module.engine) as db:
        if state == "fullgift":
            card = issue_card(db, institute, GiftCardIssue(amount="20", valid_days=30, reason="Explicit gift credit", idempotency_key="gift"), "manager")
            allocate(db, institute, card.id, AllocationCreate(ticket_id=ticket, amount="10.35", idempotency_key="funding"), "operator")
        elif state == "currency":
            db.get(QueueTicket, ticket).currency = None
        else:
            db.get(QueueTicket, ticket).status = state
        db.commit()
        with pytest.raises(HTTPException):
            persist_intent(db, request(institute, ticket), OperationKind.AUTHORIZE, "provider", "account")



@pytest.mark.parametrize("unit,total", [(None, "10.35"), ("-1", "10.35"), ("10.35", "11.35")])
def test_authorization_rejects_missing_or_inconsistent_line_quote(client, unit, total):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, line, customer = setup(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    with Session(main_module.engine) as db:
        db.get(TicketLine, line).unit_price = Decimal(unit) if unit is not None else None
        db.get(TicketLine, line).total = Decimal(total)
        db.commit()
        with pytest.raises(HTTPException):
            persist_intent(db, request(institute, ticket), OperationKind.AUTHORIZE, "provider", "account")
