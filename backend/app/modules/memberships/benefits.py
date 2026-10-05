from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select
from app.modules.commerce.models import PackageRedemption
from app.modules.memberships.models import MembershipBenefit
from app.modules.memberships.service import membership_view, scoped_membership
from app.modules.services.repository import get_service
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.repository import lock_institute
from app.modules.tickets.events import record_event
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


def checkout_line(db, institute, line_id):
    line = db.get(TicketLine, line_id)
    ticket = db.get(QueueTicket, line.ticket_id) if line else None
    if ticket is None or ticket.institute_id != institute:
        raise not_found("Ligne de caisse introuvable")
    db.refresh(ticket)
    db.refresh(line)
    if ticket.status not in {"ready_for_checkout", "in_checkout"}:
        raise business_error("Avantage modifiable uniquement avant le paiement en caisse")
    return ticket, line


def update_total(db, ticket):
    db.flush()
    ticket.total_amount = sum((row.total or Decimal("0") for row in db.scalars(
        select(TicketLine).where(TicketLine.ticket_id == ticket.id))), Decimal("0"))


def apply_benefit(db, institute, identifier, payload, actor):
    lock_institute(db, institute)
    existing = db.scalar(select(MembershipBenefit).where(MembershipBenefit.institute_id == institute,
                                       MembershipBenefit.idempotency_key == payload.idempotency_key))
    if existing:
        if (existing.membership_id, existing.ticket_line_id) != (identifier, payload.ticket_line_id):
            raise business_error("Cette cle appartient a un autre avantage")
        return existing
    membership = scoped_membership(db, institute, identifier)
    now = utcnow()
    if membership_view(membership, now)["status"] != "active":
        raise business_error("Abonnement actif requis")
    ticket, line = checkout_line(db, institute, payload.ticket_line_id)
    if ticket.customer_id != membership.customer_id or not line.performed_by_employee_id:
        raise business_error("La cliente et la prestation realisee doivent correspondre a l'abonnement")
    if db.scalar(select(PackageRedemption.id).where(PackageRedemption.ticket_line_id == line.id,
                                                   PackageRedemption.reversed_at.is_(None))):
        raise business_error("Cette prestation est deja couverte par un forfait")
    if db.scalar(select(MembershipBenefit.id).where(MembershipBenefit.ticket_line_id == line.id,
                                                    MembershipBenefit.reversed_at.is_(None))):
        raise business_error("Un avantage est deja applique a cette prestation")
    catalog = get_service(db, line.service_id)
    if catalog is None or catalog.price_member is None:
        raise business_error("Tarif membre declare requis pour cette prestation")
    price = Decimal(str(catalog.price_member))
    if (not price.is_finite() or line.unit_price is None or line.total is None
            or not Decimal(str(line.unit_price)).is_finite() or not Decimal(str(line.total)).is_finite()):
        raise business_error("Prix de prestation valides requis")
    price = price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total = (price * line.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if line.quantity <= 0 or price < 0 or price >= line.unit_price or total >= line.total:
        raise business_error("Le tarif membre doit reduire le prix de cette prestation")
    benefit = MembershipBenefit(id=new_id("mb"), institute_id=institute, membership_id=membership.id,
        ticket_line_id=line.id, quantity=line.quantity, original_unit_price=line.unit_price,
        original_total=line.total, member_unit_price=price, member_total=total,
        occurred_at=now, idempotency_key=payload.idempotency_key, actor_id=actor)
    line.unit_price, line.total = price, total
    db.add(benefit)
    update_total(db, ticket)
    record_event(db, ticket, "commerce.member_benefit_applied", ticket.status, line.performed_by_employee_id)
    db.commit()
    db.refresh(benefit)
    return benefit


def reverse_benefit(db, institute, identifier, reason, actor):
    lock_institute(db, institute)
    benefit = db.scalar(select(MembershipBenefit).where(MembershipBenefit.id == identifier,
                                                       MembershipBenefit.institute_id == institute))
    if benefit is None:
        raise not_found("Avantage introuvable")
    db.refresh(benefit)
    if benefit.reversed_at is not None:
        if benefit.reversal_reason != reason:
            raise business_error("Avantage deja annule avec un autre motif")
        return benefit
    ticket, line = checkout_line(db, institute, benefit.ticket_line_id)
    line.unit_price, line.total = benefit.original_unit_price, benefit.original_total
    benefit.reversed_at, benefit.reversed_by, benefit.reversal_reason = utcnow(), actor, reason
    update_total(db, ticket)
    record_event(db, ticket, "commerce.member_benefit_reversed", ticket.status, line.performed_by_employee_id)
    db.commit()
    db.refresh(benefit)
    return benefit
