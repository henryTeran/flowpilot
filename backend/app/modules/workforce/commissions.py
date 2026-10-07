"""Signed immutable source-linked commissions, separate correction and recovery."""
from datetime import datetime
from typing import Annotated
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, StringConstraints, AwareDatetime, field_validator, model_validator
from sqlalchemy import select, func
from app.modules.workforce.models import EmployeeCommission as Original, CommissionCancellation as Cancellation
from app.modules.workforce.absence_schemas import AbsenceCancel, Reason, Key
from app.modules.workforce.commission_sources import CommissionCalculation, calculate, capture
from app.modules.workforce.commission_rule_schemas import CommissionRuleRead, calculation_terms
from app.modules.workforce import commission_rules
from app.modules.workforce.certifications import signed_actor
from app.modules.workforce.objectives import require_employee
from app.modules.workforce.schemas import MatrixPage
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow, explicit_utc_instant

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class CommissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule_id: Identifier
    line_id: Identifier
    reason: Reason
    idempotency_key: Key


class CancellationRead(AbsenceCancel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    institute_id: str
    commission_id: str
    actor_id: str
    created_at: AwareDatetime

    @field_validator("created_at", mode="before")
    @classmethod
    def aware(cls, value): return explicit_utc_instant(value) if isinstance(value, datetime) else value


class CommissionRead(CommissionCreate):
    id: str
    institute_id: str
    employee_id: str
    ticket_id: str
    actor_id: str
    created_at: AwareDatetime
    rule_capture: CommissionRuleRead
    calculation: CommissionCalculation
    cancellation: CancellationRead | None = None

    @model_validator(mode="after")
    def pinned_authority(self):
        source, rule = self.calculation.source, self.rule_capture
        if (rule.id != self.rule_id or rule.institute_id != self.institute_id or rule.employee_id != self.employee_id
            or rule.cancellation is not None or source.institute_id != self.institute_id or source.employee_id != self.employee_id
            or source.line_id != self.line_id or source.ticket_id != self.ticket_id or source.captured_at != self.created_at
            or rule.created_at > self.created_at or calculation_terms(rule) != self.calculation.terms):
            raise ValueError("The original commission authorities disagree")
        try: verified = calculate(self.calculation.terms, source)
        except HTTPException as error: raise ValueError("The pinned commission calculation is invalid") from error
        if verified != self.calculation:
            raise ValueError("The pinned exact commission calculation disagrees")
        if self.cancellation and (self.cancellation.institute_id != self.institute_id or self.cancellation.commission_id != self.id
            or self.cancellation.created_at < self.created_at):
            raise ValueError("The cancellation does not belong to the original commission")
        return self


class CommissionPage(BaseModel):
    institute_id: str
    employee_id: str
    generated_at: AwareDatetime
    page: MatrixPage
    rows: list[CommissionRead]


def dto(row, cancellation=None):
    result = CommissionRead(id=row.id, institute_id=row.institute_id, employee_id=row.employee_id, ticket_id=row.ticket_id,
        rule_id=row.rule_id, line_id=row.line_id, reason=row.reason, idempotency_key=row.idempotency_key, actor_id=row.actor_id,
        created_at=explicit_utc_instant(row.created_at), rule_capture=row.rule_capture, calculation=row.calculation,
        cancellation=CancellationRead.model_validate(cancellation) if cancellation else None)
    if result.calculation.source.currency != row.currency or result.calculation.amount_minor != row.amount_minor:
        raise ValueError("The retained commission money disagrees with its pinned calculation")
    return result


def require(db, institute, identifier):
    row = db.scalar(select(Original).where(Original.institute_id == institute, Original.id == identifier))
    if row is None: raise not_found("Commission introuvable")
    return row


def snapshot(db, row):
    cancelled = db.scalar(select(Cancellation).where(Cancellation.institute_id == row.institute_id, Cancellation.commission_id == row.id))
    return dto(row, cancelled)


def original(db, institute, key):
    row = db.scalar(select(Original).where(Original.institute_id == institute, Original.idempotency_key == key))
    return snapshot(db, row) if row else None


def create(db, institute, payload, actor):
    signed_actor(actor); lock_institute(db, institute)
    old = original(db, institute, payload.idempotency_key)
    if old:
        if old.actor_id != actor or old.model_dump(include=set(CommissionCreate.model_fields)) != payload.model_dump():
            raise business_error("La cle conserve les conditions et l'acteur originaux")
        return old
    now = utcnow()
    rule = commission_rules.snapshot(db, commission_rules.require(db, institute, payload.rule_id))
    if rule.cancellation or rule.created_at > now:
        raise business_error("La regle originale est annulee ou son horloge est future")
    source = capture(db, institute, payload.line_id, now)
    calculation = calculate(calculation_terms(rule), source)
    active = select(Original.id).outerjoin(Cancellation,
        (Cancellation.institute_id == Original.institute_id) & (Cancellation.commission_id == Original.id)).where(
        Original.institute_id == institute, Original.line_id == source.line_id, Cancellation.id.is_(None)).limit(1)
    if db.scalar(active): raise business_error("Cette ligne possede deja une commission active")
    row = Original(id=new_id("commission"), institute_id=institute, employee_id=source.employee_id, rule_id=rule.id,
        ticket_id=source.ticket_id, line_id=source.line_id, currency=source.currency, amount_minor=calculation.amount_minor,
        rule_capture=rule.model_dump(mode="json"), calculation=calculation.model_dump(mode="json"),
        reason=payload.reason, idempotency_key=payload.idempotency_key, actor_id=actor, created_at=now)
    db.add(row); db.commit(); db.refresh(row)
    return snapshot(db, row)


def cancel(db, institute, identifier, payload, actor):
    signed_actor(actor); lock_institute(db, institute)
    old = db.scalar(select(Cancellation).where(Cancellation.institute_id == institute, Cancellation.idempotency_key == payload.idempotency_key))
    if old:
        if (old.commission_id, old.reason, old.actor_id) != (identifier, payload.reason, actor):
            raise business_error("La cle conserve les conditions et l'acteur originaux")
        return CancellationRead.model_validate(old)
    row = require(db, institute, identifier)
    if db.scalar(select(Cancellation.id).where(Cancellation.institute_id == institute, Cancellation.commission_id == identifier)):
        raise business_error("Cette commission possede deja son annulation originale")
    now = utcnow()
    if now < explicit_utc_instant(row.created_at): raise business_error("L'horloge d'annulation precede la commission originale")
    cancelled = Cancellation(id=new_id("ccancel"), institute_id=institute, commission_id=identifier,
        **payload.model_dump(), actor_id=actor, created_at=now)
    db.add(cancelled); db.commit(); db.refresh(cancelled)
    return CancellationRead.model_validate(cancelled)


def list_records(db, institute, employee, limit=20, offset=0):
    lock_institute(db, institute); require_employee(db, institute, employee)
    own = (Original.institute_id == institute, Original.employee_id == employee)
    total = db.scalar(select(func.count()).select_from(Original).where(*own))
    rows = db.execute(select(Original, Cancellation).outerjoin(Cancellation,
        (Cancellation.institute_id == Original.institute_id) & (Cancellation.commission_id == Original.id)).where(*own)
        .order_by(Original.created_at.desc(), Original.id).limit(limit).offset(offset))
    return CommissionPage(institute_id=institute, employee_id=employee, generated_at=utcnow(),
        page=MatrixPage(offset=offset, limit=limit, total=total), rows=[dto(row, cancelled) for row, cancelled in rows])
