from decimal import Decimal, localcontext
import pytest
from sqlalchemy.orm import Session
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.service import get_chiffres_by_employee
from app.shared.ids import new_id
from app.shared.time import utcnow
import app.main as main_module
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def seed(engine, institute, employee, care, values):
    with Session(engine) as db:
        for currency, amount in values:
            identifier = new_id("report")
            db.add(QueueTicket(id=identifier, institute_id=institute, ticket_number=identifier, status="paid", arrival_time=utcnow(), paid_at=utcnow(), paid_employee_id=employee, currency=currency))
            db.flush()
            db.add(TicketLine(id=new_id("line"), ticket_id=identifier, service_id=care, duration_minutes=10, quantity=1, unit_price=Decimal(amount), total=Decimal(amount), revenue_category="care"))
        db.commit()


def exercise(engine, institute, employee, care):
    seed(engine, institute, employee, care, [("CHF", "10.35"), ("CHF", "0.10"), ("EUR", "20.10"), (None, "30.00")])
    with Session(engine) as db, localcontext() as context:
        context.prec = 2
        report = get_chiffres_by_employee(db, institute)
    assert report.currency is None and report.totals.total is None
    assert report.totals.tickets == 4 and report.unknown_currency_tickets == 1
    assert all(row.total is None for row in report.rows)
    groups = {group.currency: group for group in report.currency_groups}
    assert groups["CHF"].totals.total == Decimal("10.45") and groups["CHF"].totals.tickets == 2
    assert groups["EUR"].totals.total == Decimal("20.10") and groups["EUR"].totals.tickets == 1
    return report


def test_currency_report_separates_historical_units_and_scopes_http(client):
    institute, employees, services = _bootstrap_reference_data(client)
    report = exercise(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    path = f"/api/v1/tickets/chiffres?institute_id={institute}"
    response = client.get(path, headers=_auth_headers(institute_id=institute))
    assert response.status_code == 200
    assert response.json()["totals"]["total"] is None
    assert response.json()["unknown_currency_tickets"] == 1
    assert {row["currency"] for row in response.json()["currency_groups"]} == {"CHF", "EUR"}
    assert {row["currency"]: row["totals"]["total"] for row in response.json()["currency_groups"]} == {"CHF": "10.45", "EUR": "20.10"}
    assert client.get(path, headers=_auth_headers(institute_id="foreign")).status_code == 403


def test_single_known_currency_keeps_a_comparable_total(client):
    institute, employees, services = _bootstrap_reference_data(client)
    seed(main_module.engine, institute, employees[0]["id"], services[0]["id"], [("EUR", "10.35"), ("EUR", "0.10")])
    with Session(main_module.engine) as db:
        report = get_chiffres_by_employee(db, institute)
    assert report.currency == "EUR" and report.totals.total == Decimal("10.45")
    assert report.unknown_currency_tickets == 0
    assert report.currency_groups[0].totals.total == report.totals.total


def test_report_currency_actual_postgresql(postgres_flow):
    exercise(*postgres_flow)


def test_report_serialization_preserves_cents_above_javascript_safe_integer():
    from app.modules.tickets.schemas import EmployeeChiffresRead
    row = EmployeeChiffresRead(employee_id="staff", employee_name="Employee", total=Decimal("90071992547409.93"))
    assert row.model_dump(mode="json")["total"] == "90071992547409.93"
    assert row.model_dump(mode="json")["soins"] == "0.00"
