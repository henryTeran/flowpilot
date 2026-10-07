from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.repository import lock_institute
from app.modules.workforce.commission_sources import CommissionTerms, capture, calculate, exact_minor
from test_workforce_absences_11b import setup
from test_postgres_scheduling_4d import postgres_flow

NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


def terms(employee, **changes):
    return CommissionTerms(employee_id=employee, basis="closed_attributed_line_gross", currency="CHF", category="care",
        service_id=None, rate_basis_points=1000, rounding="half_up", period_start=NOW-timedelta(days=1), period_end=NOW,
        **changes)


def exercise(engine, institute, employee, service):
    with Session(engine) as db:
        ticket = QueueTicket(id="commission-source-ticket", institute_id=institute, ticket_number="C1", status="paid",
            arrival_time=NOW-timedelta(hours=2), paid_at=NOW-timedelta(hours=1), currency="CHF",
            paid_employee_id="different-cashier", checkout_employee_id="different-cashier")
        db.add(ticket); db.flush()
        line = TicketLine(id="commission-source-line", ticket_id=ticket.id, service_id=service, quantity=3,
            duration_minutes=10, total=Decimal("10.35"), performed_by_employee_id=employee, revenue_category="care")
        db.add(line); db.commit(); lock_institute(db, institute)
        original = capture(db, institute, line.id, NOW)
        result = calculate(terms(employee), original)
        assert result.amount_minor == "104" and result.unrounded_numerator == "1035000"
        assert result.rounding_remainder == 5000 and original.gross_minor == "1035"  # No second quantity multiplication.
        assert original.employee_id == employee and "cashier" not in str(original.model_dump())
        for target, field, invalid in [(line, "total", None), (line, "total", Decimal("-1")),
            (line, "performed_by_employee_id", None), (line, "performed_by_employee_id", "foreign"),
            (line, "quantity", 0), (ticket, "currency", None), (ticket, "paid_at", None),
            (ticket, "paid_at", NOW+timedelta(microseconds=1)), (ticket, "paid_at", NOW-timedelta(hours=3)),
            (ticket, "status", "in_checkout")]:
            previous = getattr(target, field); setattr(target, field, invalid); db.flush()
            with pytest.raises(HTTPException): capture(db, institute, line.id, NOW)
            setattr(target, field, previous); db.flush()
        line.invoice_removed_at = NOW; line.invoice_removed_by_actor = "signed"; line.invoice_removal_reason = "not_performed"; db.flush()
        with pytest.raises(HTTPException): capture(db, institute, line.id, NOW)
        with pytest.raises(HTTPException) as failure: capture(db, "foreign", line.id, NOW)
        assert failure.value.status_code == 404
        line.total = Decimal("99.99"); line.quantity = 5; db.flush()
        assert calculate(terms(employee), original) == result  # Captured authority survives later source changes.
        with pytest.raises(HTTPException): capture(db, institute, line.id, NOW.replace(tzinfo=None))
        for changes in [dict(employee_id="foreign"), dict(currency="EUR"), dict(category="product"),
            dict(service_id="foreign"), dict(period_start=original.paid_at+timedelta(microseconds=1)),
            dict(period_end=original.paid_at)]:
            policy = CommissionTerms.model_validate({**terms(employee).model_dump(), **changes})
            with pytest.raises(HTTPException): calculate(policy, original)
        assert calculate(CommissionTerms.model_validate({**terms(employee).model_dump(), "period_start": original.paid_at}), original).amount_minor == "104"
        return original


def test_sqlite_commission_source_ownership_retained_closure_and_capture(client):
    institute, employee, service, _, _ = setup(client)
    exercise(main_module.engine, institute, employee, service)


def test_actual_postgres_commission_source_contract(postgres_flow):
    exercise(*postgres_flow)


def test_exact_commission_arithmetic_explicit_terms_and_rounding(client):
    institute, employee, service, _, _ = setup(client)
    source = exercise(main_module.engine, institute, employee, service)
    with localcontext() as context:
        context.prec = 2
        for gross, rate, rounding, expected in [("1035", 1000, "half_up", "104"), ("1035", 1000, "half_even", "104"),
            ("1025", 1000, "half_even", "102"), ("1025", 1000, "half_up", "103"), ("1035", 1000, "down", "103"),
            ("1", 4999, "half_up", "0"), ("1", 5001, "half_up", "1"), ("9999999999", 10000, "down", "9999999999"),
            ("1035", 0, "half_up", "0")]:
            policy = CommissionTerms.model_validate({**terms(employee).model_dump(), "rate_basis_points": rate, "rounding": rounding})
            assert calculate(policy, source.model_copy(update={"gross_minor": gross})).amount_minor == expected
        for amount, expected in [("10.3500", 1035), ("0.00", 0), ("99999999.99", 9999999999), ("1E+2", 10000)]:
            assert exact_minor(Decimal(amount)) == expected
        for bad in [None, True, 1.23, "NaN", "Infinity", "-0.01", "100000000", "0.001", "1.0001", "not-money"]:
            with pytest.raises(HTTPException): exact_minor(bad)
    for changes in [dict(rate_basis_points=True), dict(rate_basis_points=1.5), dict(rate_basis_points="1000"),
        dict(rate_basis_points=-1), dict(rate_basis_points=10001), dict(rounding="implicit"), dict(currency=None),
        dict(period_start=0), dict(period_start="0"), dict(period_start=NOW.replace(tzinfo=None)), dict(period_end=NOW-timedelta(days=1)), dict(basis="net")]:
        with pytest.raises(ValidationError): CommissionTerms.model_validate({**terms(employee).model_dump(), **changes})
    for field in ["rate_basis_points", "rounding", "currency", "service_id"]:
        value = terms(employee).model_dump(); value.pop(field)
        with pytest.raises(ValidationError): CommissionTerms.model_validate(value)
