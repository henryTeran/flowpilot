"""Ticket-scoped recovery view; absence of outcome means unknown, not failure."""
from sqlalchemy import select
from app.modules.payments.models import PaymentIntent, PaymentExecution, ParentOperationExecution, RefundExecution, PaymentOutcome, ParentOperationOutcome, RefundOutcome, CaptureApplication, RefundLoyaltyDecision
from app.modules.tickets.models import QueueTicket
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import not_found


def ticket_payment_snapshot(db, institute_id, ticket_id):
    lock_institute(db, institute_id)
    ticket = db.scalar(select(QueueTicket).where(QueueTicket.id == ticket_id, QueueTicket.institute_id == institute_id))
    if ticket is None:
        raise not_found("Ticket de paiement introuvable")
    intents = list(db.scalars(select(PaymentIntent).where(PaymentIntent.institute_id == institute_id,
        PaymentIntent.ticket_id == ticket_id).order_by(PaymentIntent.created_at, PaymentIntent.id)))
    ids = [row.id for row in intents]
    executions = {}
    for model in (PaymentExecution, ParentOperationExecution, RefundExecution):
        executions.update({row.intent_id: row for row in db.scalars(select(model).where(model.intent_id.in_(ids)).execution_options(populate_existing=True))})
    outcomes = {}
    for model in (PaymentOutcome, ParentOperationOutcome, RefundOutcome):
        for row in db.scalars(select(model).where(model.intent_id.in_(ids))):
            if row.intent_id not in outcomes or row.status != "pending":
                outcomes[row.intent_id] = row.status
    decisions = {row.refund_intent_id: row for row in db.scalars(select(RefundLoyaltyDecision).where(
        RefundLoyaltyDecision.institute_id == institute_id, RefundLoyaltyDecision.ticket_id == ticket_id))}
    application = db.get(CaptureApplication, ticket_id)
    protected = any(isinstance(row, PaymentExecution) and row.released_at is None for row in executions.values())
    operations = []
    for row in intents:
        execution = executions.get(row.id)
        operations.append(dict(id=row.id, kind=row.kind, amount=row.amount, currency=row.currency,
            provider=row.provider, account_id=row.account_id, idempotency_key=row.idempotency_key,
            actor_id=row.actor_id, status=outcomes.get(row.id, "unknown" if execution else "prepared"),
            applied=application is not None and application.intent_id == row.id,
            active_protection=isinstance(execution, PaymentExecution) and execution.released_at is None,
            loyalty_decision=decisions.get(row.id)))
    return dict(ticket_id=ticket_id, protected=protected, operations=operations)
