from datetime import date, timedelta
from decimal import Decimal, localcontext
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.institutes.models import Institute
from app.modules.institutes.calendar import day_bounds
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.workforce.revenue import read, EmployeeRevenue
from app.shared.ids import new_id
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def fixture(engine, institute, employee, service):
    day = date(2026, 10, 25)
    with Session(engine) as db:
        db.get(Institute, institute).timezone = "Europe/Zurich"
        db.commit()
        start, end = day_bounds(db, institute, day)
        for index, (currency, amount, performer, status, instant) in enumerate([
            ("CHF", "10.35", employee, "paid", start), ("CHF", "0.10", employee, "paid", start+timedelta(hours=24)),
            ("EUR", "20.10", employee, "paid", start), (None, "30.00", employee, "paid", start),
            ("EUR", None, employee, "paid", start), ("CHF", "99.00", None, "paid", start),
            ("CHF", "88.00", employee, "in_checkout", start), ("CHF", "77.00", employee, "paid", end),
            ("CHF", "55.00", employee, "paid", start)]):
            identifier = new_id("revenue")
            ticket = QueueTicket(id=identifier, institute_id=institute, ticket_number=identifier, status=status,
                arrival_time=instant, paid_at=instant, paid_employee_id=employee, checkout_employee_id=employee, currency=currency)
            db.add(ticket); db.flush()
            db.add(TicketLine(id=new_id("line"), ticket_id=identifier, service_id=service, quantity=1, duration_minutes=10,
                total=Decimal(amount) if amount else None, unit_price=Decimal(amount) if amount else None,
                performed_by_employee_id=performer, revenue_category="care",
                invoice_removed_at=instant if index == 8 else None, invoice_removed_by_actor="signed" if index == 8 else None,
                invoice_removal_reason="not_performed" if index == 8 else None))
        db.commit()
    return day


def check(engine, institute, employee, day):
    with Session(engine) as db, localcontext() as context:
        context.prec = 2
        report = EmployeeRevenue.model_validate(read(db, institute, employee, day, 2, 2))
    assert report.end-report.start == timedelta(hours=25)
    assert report.page.total == 5 and len(report.rows) == 2
    assert report.institute_unattributed_lines == 1  # Cashier is not inferred as performer.
    groups = {row.currency: row for row in report.currencies}
    assert groups["CHF"].total == Decimal("10.45") and groups["CHF"].ticket_count == 2
    assert groups["EUR"].total is None and groups["EUR"].amount_known_total == Decimal("20.10")
    assert groups["EUR"].amount_missing_lines == 1
    assert groups[None].total is None and groups[None].amount_known_total is None
    assert all(row.employee_id == employee for row in report.rows)
    return report


def test_employee_revenue_closed_source_exact_money_ownership_and_paging(client):
    institute, employee, service, base, headers = setup(client)
    day = fixture(main_module.engine, institute, employee, service)
    check(main_module.engine, institute, employee, day)
    path = f"{base}/employees/{employee}/revenue?day={day}&limit=2&offset=2"
    reply = client.get(path, headers=headers)
    assert reply.status_code == 200, reply.text
    assert reply.json()["currencies"][0]["currency"] is None
    assert {row["currency"]: row["total"] for row in reply.json()["currencies"]}["CHF"] == "10.45"
    assert client.get(path, headers=_auth_headers("accueil", institute)).status_code == 403
    assert client.get(path, headers=_auth_headers("responsable_institut", "foreign")).status_code == 403
    assert client.get(f"{base}/employees/foreign/revenue?day={day}", headers=headers).status_code == 404
    assert client.get(f"{base}/employees/{employee}/revenue?day={day}&limit=101", headers=headers).status_code == 422


def test_actual_postgres_employee_revenue_decimal_and_calendar(postgres_flow):
    engine, institute, employee, service = postgres_flow
    check(engine, institute, employee, fixture(engine, institute, employee, service))
