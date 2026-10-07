"""Read observed registered-customer billing, under the shared institute lock."""
from datetime import timezone
from app.shared.money import amount_fact

from pydantic import ValidationError
from sqlalchemy import select

from app.modules.crm.metrics import BillingWindow, ClosedTicketFact, calculate_billing
from app.modules.customers.repository import require_customer
from app.modules.tickets.models import QueueTicket
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error
from app.shared.time import explicit_utc_instant, utcnow



def read(db, institute, customer, start, end):
    lock_institute(db, institute)
    require_customer(db, institute, customer)
    try:
        window = BillingWindow(institute_id=institute, customer_id=customer,
            start=start, end=end, captured_at=utcnow())
    except ValidationError as error:
        raise business_error("An explicit positive observed billing window is required") from error
    return capture(db, window)


def capture(db, window: BillingWindow):
    """Caller holds the shared lock and pins owner, horizon and capture clock."""
    institute, customer = window.institute_id, window.customer_id
    # No line join: a basket is the retained ticket total, already including
    # quantities and invoice corrections. Unknown paid times cannot be dated.
    rows = db.execute(select(QueueTicket.id, QueueTicket.paid_at,
        QueueTicket.currency, QueueTicket.total_amount).where(
            QueueTicket.institute_id == institute, QueueTicket.customer_id == customer,
            QueueTicket.status == "paid", QueueTicket.paid_at >= window.start.astimezone(timezone.utc),
            QueueTicket.paid_at < window.end.astimezone(timezone.utc)).order_by(QueueTicket.paid_at, QueueTicket.id)
        .execution_options(yield_per=100))

    def facts():
        for ticket, paid, currency, amount in rows:
            minor, quality = amount_fact(amount)
            yield ClosedTicketFact(institute_id=institute, customer_id=customer,
                ticket_id=ticket, closed_at=explicit_utc_instant(paid),
                captured_at=window.captured_at, currency=currency if currency in {"CHF", "EUR"} else None,
                amount_minor=minor, amount_quality=quality)

    return calculate_billing(window, facts())
