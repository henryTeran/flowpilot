"""One institute-locked capture of recorded paid baskets and active lines."""
from datetime import timezone
from pydantic import ValidationError
from sqlalchemy import select, func
from app.modules.crm.billing import amount_fact
from app.modules.revenue.billing import Billing, Window, TicketFact, LineFact, calculate
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error
from app.shared.time import explicit_utc_instant, utcnow


def read(db, institute, start, end) -> Billing:
    lock_institute(db, institute)
    try:
        window = Window(institute_id=institute, start=start, end=end, captured_at=utcnow())
    except ValidationError as error:
        raise business_error("An explicit observed revenue period is required") from error
    own = (QueueTicket.institute_id == institute, QueueTicket.status == "paid",
        QueueTicket.paid_at >= window.start.astimezone(timezone.utc),
        QueueTicket.paid_at < window.end.astimezone(timezone.utc))

    def tickets():
        for identifier, paid, currency, amount in db.execute(select(QueueTicket.id, QueueTicket.paid_at,
            QueueTicket.currency, QueueTicket.total_amount).where(*own).order_by(QueueTicket.paid_at, QueueTicket.id)
            .execution_options(yield_per=100)):
            minor, quality = amount_fact(amount)
            yield TicketFact(institute_id=institute, ticket_id=identifier, paid_at=explicit_utc_instant(paid),
                captured_at=window.captured_at, currency=currency if currency in {"CHF", "EUR"} else None,
                amount_minor=minor, amount_quality=quality)

    def lines():
        for identifier, ticket, service, category, quantity, amount in db.execute(select(TicketLine.id,
            TicketLine.ticket_id, TicketLine.service_id, TicketLine.revenue_category, TicketLine.quantity, TicketLine.total)
            .join(QueueTicket, QueueTicket.id == TicketLine.ticket_id).where(*own, TicketLine.invoice_removed_at.is_(None))
            .order_by(TicketLine.ticket_id, TicketLine.id).execution_options(yield_per=100)):
            minor, quality = amount_fact(amount)
            yield LineFact(institute_id=institute, ticket_id=ticket, line_id=identifier, service_id=service,
                captured_at=window.captured_at, category=category if category in {"care", "retail"} else None,
                quantity=quantity, amount_minor=minor, amount_quality=quality)
    try:
        result = calculate(window, tickets(), lines())
    except ValueError as error:
        raise business_error("Recorded revenue sources require verification") from error
    # Undated paid records cannot be assigned to this period. This diagnostic is
    # institute-wide; it must never be presented as a period count.
    undated = db.scalar(select(func.count()).select_from(QueueTicket).where(
        QueueTicket.institute_id == institute, QueueTicket.status == "paid", QueueTicket.paid_at.is_(None)))
    return result.model_copy(update={"institute_undated_paid_tickets": undated})
