"""Stored-value tender facts; service prices and revenue remain unchanged."""
from decimal import Decimal
from sqlalchemy import select
from app.modules.gift_cards.models import GiftCard, GiftCardAllocation, GiftTenderClosure
from app.modules.gift_cards.service import aware
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.repository import lock_institute
from app.modules.tickets.events import record_event
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


def scoped_ticket(db, institute, identifier):
    ticket = db.get(QueueTicket, identifier)
    if ticket is None or ticket.institute_id != institute:
        raise not_found("Ticket de caisse introuvable")
    db.refresh(ticket)
    return ticket


def allocations(db, ticket_id):
    return list(db.scalars(select(GiftCardAllocation).where(
        GiftCardAllocation.ticket_id == ticket_id).order_by(GiftCardAllocation.occurred_at, GiftCardAllocation.id)
        .execution_options(populate_existing=True)))


def tender_view(db, ticket):
    rows = allocations(db, ticket.id)
    total = sum((Decimal(str(line.total or 0)) for line in db.scalars(select(TicketLine).where(TicketLine.invoice_removed_at.is_(None)).where(
        TicketLine.ticket_id == ticket.id).execution_options(populate_existing=True))), Decimal("0"))
    active = [row for row in rows if row.reversed_at is None]
    if any(row.currency != ticket.currency for row in active):
        raise business_error("Devises du paiement et du ticket incompatibles")
    gift = sum((row.amount for row in active), Decimal("0"))
    if gift > total:
        raise business_error("Le paiement cadeau depasse le montant du ticket")
    closure = db.get(GiftTenderClosure, ticket.id)
    remainder = closure.remainder_amount if closure else Decimal("0")
    if closure and (closure.currency != ticket.currency or closure.gift_amount != gift
                    or gift + remainder != total):
        raise business_error("Les faits de cloture et le ticket sont incoherents")
    return dict(ticket_id=ticket.id, currency=ticket.currency, total=total,
                gift_amount=gift, remainder_amount=remainder,
                remainder_method=closure.remainder_method if closure else None,
                remaining_due=total - gift - remainder, allocations=rows)


def require_no_active_tender(db, ticket):
    from app.modules.payments.executions import require_no_payment_execution
    require_no_payment_execution(db, ticket)
    if db.scalar(select(GiftCardAllocation.id).where(GiftCardAllocation.ticket_id == ticket.id,
                                                   GiftCardAllocation.reversed_at.is_(None))):
        raise business_error("Annuler les paiements cadeaux avant de modifier ou annuler le ticket")


def validate_payment(db, ticket, method, remainder_method, actor):
    view = tender_view(db, ticket)
    if method not in {"carte_cadeau", "mixte"}:
        if view["gift_amount"] or remainder_method is not None:
            raise business_error("Un paiement cadeau actif exige le mode cadeau ou mixte")
        return
    if not view["gift_amount"]:
        raise business_error("Un paiement carte cadeau enregistre est requis pour ce mode")
    if not isinstance(actor, str) or not actor.strip() or len(actor) > 160:
        raise business_error("Identite signee requise pour cloturer le paiement cadeau")
    due = view["remaining_due"]
    if method == "carte_cadeau" and (due != 0 or remainder_method is not None):
        raise business_error("La carte cadeau doit couvrir tout le ticket pour ce mode")
    if method == "mixte" and (due <= 0 or remainder_method not in {"cb", "especes", "cheque"}):
        raise business_error("Un solde positif et son mode de paiement sont requis pour le paiement mixte")
    db.add(GiftTenderClosure(ticket_id=ticket.id, institute_id=ticket.institute_id,
        currency=ticket.currency, gift_amount=view["gift_amount"], remainder_amount=due,
        remainder_method=remainder_method, actor_id=actor, occurred_at=utcnow()))


def validate_paid_replay(db, ticket, remainder_method):
    fact = db.get(GiftTenderClosure, ticket.id)
    if (fact is not None and fact.remainder_method != remainder_method) or (fact is None and remainder_method is not None):
        raise business_error("Le solde de ce paiement a deja un autre mode")


def allocate(db, institute, card_id, payload, actor):
    lock_institute(db, institute)
    old = db.scalar(select(GiftCardAllocation).where(GiftCardAllocation.institute_id == institute,
                                  GiftCardAllocation.idempotency_key == payload.idempotency_key))
    if old:
        db.refresh(old)
        if (old.card_id, old.ticket_id, old.amount) != (card_id, payload.ticket_id, payload.amount):
            raise business_error("Cette cle appartient a un autre paiement cadeau")
        return old
    ticket = scoped_ticket(db, institute, payload.ticket_id)
    from app.modules.payments.executions import require_no_payment_execution
    require_no_payment_execution(db, ticket)
    if ticket.status not in {"ready_for_checkout", "in_checkout"}:
        raise business_error("Paiement cadeau disponible uniquement avant cloture en caisse")
    card = db.get(GiftCard, card_id)
    if card is None or card.institute_id != institute:
        raise not_found("Carte cadeau introuvable")
    db.refresh(card)
    now = utcnow()
    if now >= aware(card.expires_at):
        raise business_error("Carte cadeau expiree")
    if ticket.currency is None or ticket.currency != card.currency:
        raise business_error("Devise confirmee du ticket et de la carte identique requise")
    view = tender_view(db, ticket)
    if payload.amount > card.remaining or payload.amount > view["remaining_due"]:
        raise business_error("Montant superieur au solde disponible ou au reste a payer")
    row = GiftCardAllocation(id=new_id("gpay"), institute_id=institute, card_id=card.id,
        ticket_id=ticket.id, currency=card.currency, amount=payload.amount, occurred_at=now,
        actor_id=actor, idempotency_key=payload.idempotency_key)
    card.remaining -= payload.amount
    db.add(row)
    record_event(db, ticket, "commerce.gift_allocated", ticket.status)
    db.commit()
    db.refresh(row)
    return row


def reverse(db, institute, identifier, reason, actor):
    lock_institute(db, institute)
    row = db.get(GiftCardAllocation, identifier)
    if row is None or row.institute_id != institute:
        raise not_found("Paiement cadeau introuvable")
    db.refresh(row)
    if row.reversed_at is not None:
        if row.reversal_reason != reason:
            raise business_error("Cette annulation a deja un autre motif")
        return row
    ticket = scoped_ticket(db, institute, row.ticket_id)
    from app.modules.payments.executions import require_no_payment_execution
    require_no_payment_execution(db, ticket)
    if ticket.status not in {"ready_for_checkout", "in_checkout"}:
        raise business_error("Paiement cadeau annulable uniquement avant cloture en caisse")
    card = db.get(GiftCard, row.card_id)
    db.refresh(card)
    card.remaining += row.amount
    row.reversed_at, row.reversed_by, row.reversal_reason = utcnow(), actor, reason
    record_event(db, ticket, "commerce.gift_reversed", ticket.status)
    db.commit()
    db.refresh(row)
    return row
