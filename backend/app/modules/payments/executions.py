"""Seal before I/O; never infer failure or release from a timeout."""
from sqlalchemy import select
from app.modules.payments.models import PaymentIntent, PaymentExecution
from app.modules.payments.intents import original_request, validate_prepared_authorization
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.time import utcnow


def require_no_payment_execution(db, ticket):
    if db.scalar(select(PaymentExecution.intent_id).where(
            PaymentExecution.ticket_id == ticket.id,
            PaymentExecution.released_at.is_(None))):
        raise business_error("Paiement prestataire en cours ou incertain; recuperer son resultat avant modification")


def seal_authorization(db, institute_id, intent_id):
    lock_institute(db, institute_id)
    intent = db.scalar(select(PaymentIntent).where(PaymentIntent.id == intent_id,
                                                  PaymentIntent.institute_id == institute_id))
    if intent is None:
        raise not_found("Intention de paiement introuvable")
    old = db.get(PaymentExecution, intent_id)
    if old is not None:
        # Replay always uses the original request, even after terminal release.
        return original_request(intent)
    from app.modules.tickets.models import QueueTicket
    ticket = db.get(QueueTicket, intent.ticket_id)
    require_no_payment_execution(db, ticket)
    request = validate_prepared_authorization(db, institute_id, intent_id)
    db.add(PaymentExecution(intent_id=intent_id, institute_id=institute_id,
                            ticket_id=intent.ticket_id, sealed_at=utcnow()))
    db.commit()  # The durable seal must exist before any external call.
    return request
