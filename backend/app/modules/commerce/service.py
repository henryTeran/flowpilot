from datetime import timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commerce.models import CustomerPackage, PackagePlan, PackageRedemption
from app.modules.commerce.schemas import PackageConsume, PackageIssue, PackagePlanCreate
from app.modules.services.repository import get_service
from app.modules.tickets.events import record_event
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


def package_view(package, now=None):
    now = now or utcnow()
    expiry = package.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    remaining = package.sessions - package.consumed
    status = "expired" if now >= expiry else "exhausted" if remaining == 0 else "active"
    return {field: getattr(package, field) for field in (
        "id", "institute_id", "plan_id", "customer_id", "service_id", "name", "sessions",
        "consumed", "issued_at", "expires_at")} | {
        "remaining": remaining, "usable_sessions": remaining if status == "active" else 0, "status": status}


def scoped_package(db, institute, identifier):
    package = db.scalar(select(CustomerPackage).where(CustomerPackage.id == identifier,
                                                     CustomerPackage.institute_id == institute))
    if package is None:
        raise not_found("Forfait introuvable")
    return package


def create_plan(db: Session, institute, payload: PackagePlanCreate):
    lock_institute(db, institute)
    service = get_service(db, payload.service_id)
    if service is None or service.status != "active":
        raise business_error("Prestation active requise")
    plan = PackagePlan(id=new_id("pp"), institute_id=institute, **payload.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def issue_package(db: Session, institute, payload: PackageIssue, actor):
    lock_institute(db, institute)
    existing = db.scalar(select(CustomerPackage).where(CustomerPackage.institute_id == institute,
                                                      CustomerPackage.idempotency_key == payload.idempotency_key))
    if existing:
        if (existing.plan_id, existing.customer_id) != (payload.plan_id, payload.customer_id):
            raise business_error("Cette cle de rejeu appartient a une autre attribution")
        return existing
    plan = db.scalar(select(PackagePlan).where(PackagePlan.id == payload.plan_id, PackagePlan.institute_id == institute))
    if plan is None:
        raise not_found("Cure introuvable")
    service = get_service(db, plan.service_id)
    if service is None or service.status != "active":
        raise business_error("Cette cure ne propose plus une prestation active")
    now = utcnow()
    package = CustomerPackage(id=new_id("cp"), institute_id=institute, plan_id=plan.id,
        customer_id=payload.customer_id, service_id=plan.service_id, name=plan.name,
        sessions=plan.sessions, consumed=0, issued_at=now, expires_at=now + timedelta(days=plan.valid_days),
        idempotency_key=payload.idempotency_key, actor_id=actor)
    db.add(package)
    db.commit()
    db.refresh(package)
    return package


def consume_package(db: Session, institute, identifier, payload: PackageConsume, actor):
    lock_institute(db, institute)
    package = scoped_package(db, institute, identifier)
    db.refresh(package)
    existing = db.scalar(select(PackageRedemption).where(PackageRedemption.institute_id == institute,
                                                        PackageRedemption.idempotency_key == payload.idempotency_key))
    if existing:
        if (existing.package_id, existing.ticket_line_id) != (identifier, payload.ticket_line_id):
            raise business_error("Cette cle de rejeu appartient a une autre consommation")
        return existing
    line = db.get(TicketLine, payload.ticket_line_id)
    ticket = db.get(QueueTicket, line.ticket_id) if line else None
    if not ticket or ticket.institute_id != institute:
        raise not_found("Ligne de caisse introuvable")
    db.refresh(ticket)
    db.refresh(line)
    if ticket.customer_id != package.customer_id or line.service_id != package.service_id:
        raise business_error("La cliente et la prestation doivent correspondre au forfait")
    if ticket.status not in {"ready_for_checkout", "in_checkout"} or not line.performed_by_employee_id:
        raise business_error("Consommer le forfait apres la prestation et avant le paiement")
    if db.scalar(select(PackageRedemption.id).where(PackageRedemption.ticket_line_id == line.id)):
        raise business_error("Cette prestation est deja couverte par un forfait")
    now = utcnow()
    if package_view(package, now)["usable_sessions"] < line.quantity or line.quantity <= 0:
        raise business_error("Forfait expire ou solde de seances insuffisant")
    redemption = PackageRedemption(id=new_id("pr"), institute_id=institute, package_id=package.id,
        ticket_line_id=line.id, sessions=line.quantity, original_unit_price=line.unit_price,
        original_total=line.total, occurred_at=now, idempotency_key=payload.idempotency_key, actor_id=actor)
    package.consumed += line.quantity
    line.unit_price = Decimal("0")
    line.total = Decimal("0")
    db.add(redemption)
    db.flush()
    ticket.total_amount = sum((item.total or Decimal("0") for item in db.scalars(
        select(TicketLine).where(TicketLine.ticket_id == ticket.id))), Decimal("0"))
    record_event(db, ticket, "commerce.package_redeemed", ticket.status, line.performed_by_employee_id)
    db.commit()
    db.refresh(redemption)
    return redemption
