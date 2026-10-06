"""Current unpaid quote checks, held under the institute transaction lock."""
from decimal import Decimal, localcontext
from sqlalchemy import select
from app.modules.tickets.models import TicketLine
from app.modules.gift_cards.tenders import tender_view
from app.modules.payments.provider import PaymentAmount
from app.shared.exceptions import business_error


def authorization_amount(db, ticket):
    if ticket.status not in {"ready_for_checkout", "in_checkout"}:
        raise business_error("Autorisation possible uniquement avant paiement en caisse")
    if ticket.currency not in {"CHF", "EUR"}:
        raise business_error("Devise confirmee requise pour autoriser le paiement")
    lines = list(db.scalars(select(TicketLine).where(TicketLine.invoice_removed_at.is_(None)).where(TicketLine.ticket_id == ticket.id)
                           .execution_options(populate_existing=True)))
    if not lines:
        raise business_error("Prestations chiffrees requises pour le paiement")
    with localcontext() as context:
        context.prec = 28
        for line in lines:
            if line.unit_price is None or line.total is None or line.quantity <= 0:
                raise business_error("Prix et quantite declares requis pour le paiement")
            unit, total = Decimal(str(line.unit_price)), Decimal(str(line.total))
            if not unit.is_finite() or not total.is_finite() or unit < 0 or total < 0 or unit * line.quantity != total:
                raise business_error("Prix de prestation incoherents pour le paiement")
        due = tender_view(db, ticket)["remaining_due"]
    if due <= 0:
        raise business_error("Aucun montant positif restant a autoriser")
    try:
        return PaymentAmount(due, ticket.currency)
    except ValueError as reason:
        raise business_error("Montant restant hors des limites du paiement") from reason
