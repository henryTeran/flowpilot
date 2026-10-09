"""Opt-in historical observed invoices in the owned new browser database.

No clock patch, payment adapter or production mutation route. Records exercise
reading legacy snapshots, not historical checkout execution or bank settlement.
"""
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.modules.tickets.models import QueueTicket, TicketLine


def seed_revenue(engine, institute):
    with Session(engine) as db:
        for index, (currency, amount) in enumerate((("CHF", "19.99"), ("CHF", "0.01"), ("EUR", "7.25"), (None, "8.00"), ("CHF", None))):
            identifier = f"browser-revenue-{index}"
            occurred = datetime(2025, 10, 26, 1, index, tzinfo=timezone.utc)
            db.add(QueueTicket(id=identifier, institute_id=institute, ticket_number=identifier,
                status="paid", arrival_time=occurred, paid_at=occurred, currency=currency,
                total_amount=Decimal(amount) if amount else None, payment_method="especes"))
        db.flush()
        for index, (ticket, category, amount) in enumerate(((0, "care", "12.34"), (0, "retail", "7.65"), (1, "retail", "0.01"), (2, "care", "7.25"))):
            db.add(TicketLine(id=f"browser-revenue-line-{index}", ticket_id=f"browser-revenue-{ticket}",
                service_id="svc-aisselles", quantity=1, unit_price=Decimal(amount), total=Decimal(amount),
                duration_minutes=10 if category == "care" else 0, revenue_category=category))
        db.commit()


def read_revenue_snapshot(engine):
    with Session(engine) as db:
        return dict(tickets=[dict(id=row.id, status=row.status, currency=row.currency, amount=str(row.total_amount), paid_at=str(row.paid_at))
            for row in db.scalars(select(QueueTicket).where(QueueTicket.id.like("browser-revenue-%")).order_by(QueueTicket.id))],
            lines=[dict(id=row.id, ticket_id=row.ticket_id, category=row.revenue_category, quantity=row.quantity, total=str(row.total), removed_at=str(row.invoice_removed_at))
            for row in db.scalars(select(TicketLine).where(TicketLine.id.like("browser-revenue-line-%")).order_by(TicketLine.id))])
