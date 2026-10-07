"""Read observed registered-customer billing, under the shared institute lock."""
from datetime import timezone
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError
from sqlalchemy import select

from app.modules.crm.metrics import BillingWindow, ClosedTicketFact, calculate_billing
from app.modules.customers.repository import require_customer
from app.modules.tickets.models import QueueTicket
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error
from app.shared.time import explicit_utc_instant, utcnow


def amount_fact(value):
    """Preserve absent/invalid Numeric(10,2) without float or context rounding."""
    if value is None:
        return None, "missing"
    if not isinstance(value, (Decimal, str)):
        return None, "invalid"
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return None, "invalid"
    if not amount.is_finite() or amount < 0 or amount > Decimal("99999999.99"):
        return None, "invalid"
    if amount.is_zero():
        return "0", "known"
    _, digits, exponent = amount.as_tuple()
    if exponent < -2:
        extra = -2-exponent
        if extra >= len(digits) or any(digits[-extra:]):
            return None, "invalid"
        digits = digits[:-extra]
        exponent = -2
    coefficient = int("".join(map(str, digits)))
    return str(coefficient * 10**(exponent+2)), "known"


def read(db, institute, customer, start, end):
    lock_institute(db, institute)
    require_customer(db, institute, customer)
    try:
        window = BillingWindow(institute_id=institute, customer_id=customer,
            start=start, end=end, captured_at=utcnow())
    except ValidationError as error:
        raise business_error("An explicit positive observed billing window is required") from error
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
