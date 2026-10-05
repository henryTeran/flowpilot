"""Explicit invoice denomination, without conversion or inference from geography."""
from app.modules.gift_cards.models import GiftCardSettings
from app.modules.tickets.models import TicketCurrencyFact
from app.modules.tickets.repository import lock_ticket
from app.modules.tickets.events import record_event
from app.shared.exceptions import business_error
from app.shared.ids import new_id
from app.shared.time import utcnow


def snapshot_currency(db, ticket):
    # The caller owns the institute lock and commits the entire ticket transaction.
    settings = db.get(GiftCardSettings, ticket.institute_id)
    if settings is None:
        return
    db.refresh(settings)
    ticket.currency = settings.currency
    db.add(TicketCurrencyFact(id=new_id("currency"), institute_id=ticket.institute_id,
        ticket_id=ticket.id, currency=settings.currency, source="institute_settings",
        reason="Devise configuree lors de la creation du ticket", actor_id=settings.actor_id,
        occurred_at=ticket.arrival_time))


def confirm_currency(db, identifier, currency, reason, actor):
    ticket = lock_ticket(db, identifier)
    if ticket.currency is not None:
        if ticket.currency != currency:
            raise business_error("La devise enregistree du ticket ne peut pas changer")
        return ticket
    if ticket.status not in {"ready_for_checkout", "in_checkout"}:
        raise business_error("Confirmer la devise uniquement sur un ticket non paye en caisse")
    settings = db.get(GiftCardSettings, ticket.institute_id)
    if settings is None:
        raise business_error("Configurer la devise de l'institut avant sa confirmation")
    db.refresh(settings)
    if settings.currency != currency:
        raise business_error("La devise doit correspondre a la configuration explicite de l'institut")
    ticket.currency = currency
    db.add(TicketCurrencyFact(id=new_id("currency"), institute_id=ticket.institute_id,
        ticket_id=ticket.id, currency=currency, source="cashier_confirmation",
        reason=reason, actor_id=actor, occurred_at=utcnow()))
    record_event(db, ticket, "commerce.currency_confirmed", ticket.status)
    db.commit()
    db.refresh(ticket)
    return ticket


def require_current_catalog_currency(db, ticket):
    """A current catalog quote must not be relabeled into a different invoice unit."""
    settings = db.get(GiftCardSettings, ticket.institute_id)
    if settings is None:
        if ticket.currency is not None:
            raise business_error("Configuration de devise requise pour ce devis")
        return  # Preserve the existing wholly unconfigured legacy workflow.
    db.refresh(settings)
    if ticket.currency is None:
        raise business_error("Confirmer la devise du ticket avant d'appliquer un nouveau tarif")
    if ticket.currency != settings.currency:
        raise business_error("Le tarif courant et le ticket ont des devises differentes")
