"""Apply confirmed capture and ordinary checkout effects in one transaction."""
from decimal import localcontext
from sqlalchemy import select
from app.modules.payments.models import PaymentIntent, ParentOperationExecution, ParentOperationOutcome, PaymentExecution, CaptureApplication
from app.modules.payments.provider import PaymentAmount, identifier
from app.modules.payments.quotes import authorization_amount
from app.modules.tickets.models import QueueTicket
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.time import utcnow


def apply_capture(db, institute_id, intent_id, employee_id, actor_id, method):
    identifier(actor_id, 160)
    if method not in {"cb", "especes", "cheque"}:
        raise business_error("Mode explicite du paiement capture requis")
    lock_institute(db, institute_id)
    intent = db.scalar(select(PaymentIntent).where(PaymentIntent.id == intent_id,
                                                  PaymentIntent.institute_id == institute_id))
    if intent is None:
        raise not_found("Intention de paiement introuvable")
    if intent.kind != "capture" or intent.actor_id != actor_id:
        raise business_error("Capture et identite initiale correspondantes requises")
    ticket = db.get(QueueTicket, intent.ticket_id)
    db.refresh(ticket)
    old = db.get(CaptureApplication, ticket.id)
    if old is not None:
        if (old.intent_id, old.employee_id, old.actor_id, old.method) != (intent_id, employee_id, actor_id, method):
            raise business_error("Cette capture a deja une autre application en caisse")
        return ticket
    execution = db.get(ParentOperationExecution, intent_id)
    fact = db.scalar(select(ParentOperationOutcome).where(ParentOperationOutcome.intent_id == intent_id,
                                                        ParentOperationOutcome.status == "captured"))
    if execution is None or fact is None:
        raise business_error("Capture confirmee requise avant cloture")
    parent = db.get(PaymentExecution, execution.parent_intent_id)
    db.refresh(parent)
    if parent.released_at is not None:
        raise business_error("Protection initiale de la capture requise")
    if PaymentAmount(fact.amount, fact.currency) != authorization_amount(db, ticket):
        raise business_error("Capture et reste a payer incoherents")
    from app.modules.gift_cards.tenders import tender_view
    with localcontext() as context:
        context.prec = 28
        mixed = tender_view(db, ticket)["gift_amount"] > 0
        from app.modules.tickets.service import complete_payment
        try:
            db.add(CaptureApplication(ticket_id=ticket.id, intent_id=intent_id, institute_id=institute_id,
                  employee_id=employee_id, actor_id=actor_id, method=method, applied_at=utcnow()))
            parent.released_at = utcnow()
            db.flush()
            return complete_payment(db, ticket.id, employee_id, "mixte" if mixed else method,
                           remainder_method=method if mixed else None, actor=actor_id,
                           operator_institute=institute_id)
        except Exception:
            db.rollback()
            raise
