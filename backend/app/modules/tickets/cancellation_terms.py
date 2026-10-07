"""Commercial conditions retained with a new terminal cancellation event."""
from datetime import timezone
from hashlib import sha256
import json
from sqlalchemy import select
from app.modules.tickets.models import TicketLine
from app.shared.money import amount_fact


def fingerprint(terms):
    return sha256(json.dumps(terms, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")).hexdigest()


def capture(db, ticket, previous_status, at, actor):
    minor, quality = amount_fact(ticket.total_amount)
    lines = []
    for line in db.scalars(select(TicketLine).where(TicketLine.ticket_id == ticket.id)
        .order_by(TicketLine.id).execution_options(populate_existing=True)):
        total, total_quality = amount_fact(line.total)
        unit, unit_quality = amount_fact(line.unit_price)
        lines.append(dict(id=line.id, service_id=line.service_id, quantity=line.quantity,
            duration_minutes=line.duration_minutes, category=line.revenue_category,
            unit_minor=unit, unit_quality=unit_quality, total_minor=total, total_quality=total_quality,
            removed_at=line.invoice_removed_at.astimezone(timezone.utc).isoformat() if line.invoice_removed_at and line.invoice_removed_at.tzinfo else
                line.invoice_removed_at.replace(tzinfo=timezone.utc).isoformat() if line.invoice_removed_at else None))
    terms = dict(institute_id=ticket.institute_id, ticket_id=ticket.id, customer_id=ticket.customer_id,
        previous_status=previous_status, status="cancelled", occurred_at=at.astimezone(timezone.utc).isoformat(),
        actor_id=actor, currency=ticket.currency if ticket.currency in {"CHF", "EUR"} else None,
        amount_minor=minor, amount_quality=quality, lines=lines,
        basis="recorded_commercial_terms_at_cancellation", realized_revenue=False, causal_loss_proven=False)
    return dict(terms=terms, fingerprint=fingerprint(terms))
