from sqlalchemy import func, select
from app.modules.employees.models import Employee
from app.modules.tickets.repository import lock_institute
from app.modules.workforce.models import EmployeeCertification, CertificationRevocation
from app.modules.workforce.certification_schemas import CertificationRead, RevocationRead
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


def signed_actor(actor):
    if not isinstance(actor, str) or not actor.strip() or len(actor) > 160:
        raise business_error("Un acteur signe est requis")


def require(db, institute, identifier):
    row = db.scalar(select(EmployeeCertification).where(EmployeeCertification.institute_id == institute,
                                                        EmployeeCertification.id == identifier))
    if row is None:
        raise not_found("Certification introuvable")
    return row


def snapshot(db, row):
    result = CertificationRead.model_validate(row)
    revocation = db.scalar(select(CertificationRevocation).where(CertificationRevocation.institute_id == row.institute_id,
                                      CertificationRevocation.certification_id == row.id))
    result.revocation = RevocationRead.model_validate(revocation) if revocation else None
    return result


def create(db, institute, payload, actor):
    signed_actor(actor)
    lock_institute(db, institute)
    old = db.scalar(select(EmployeeCertification).where(EmployeeCertification.institute_id == institute,
                                      EmployeeCertification.idempotency_key == payload.idempotency_key))
    if old:
        original = CertificationRead.model_validate(old).model_dump(include=set(type(payload).model_fields))
        if original != payload.model_dump() or old.actor_id != actor:
            raise business_error("La cle de certification conserve ses conditions et son acteur originaux")
        return snapshot(db, old)
    if not db.scalar(select(Employee.id).where(Employee.institute_id == institute, Employee.id == payload.employee_id)):
        raise not_found("Collaboratrice introuvable")
    row = EmployeeCertification(id=new_id("cert"), institute_id=institute, **payload.model_dump(),
                                actor_id=actor, created_at=utcnow())
    db.add(row)
    db.commit()
    db.refresh(row)
    return snapshot(db, row)


def revoke(db, institute, identifier, payload, actor):
    signed_actor(actor)
    lock_institute(db, institute)
    old = db.scalar(select(CertificationRevocation).where(CertificationRevocation.institute_id == institute,
                                   CertificationRevocation.idempotency_key == payload.idempotency_key))
    if old:
        if (old.certification_id, old.reason, old.actor_id) != (identifier, payload.reason, actor):
            raise business_error("La cle de revocation conserve ses conditions et son acteur originaux")
        return RevocationRead.model_validate(old)
    require(db, institute, identifier)
    if db.scalar(select(CertificationRevocation.id).where(CertificationRevocation.institute_id == institute,
                                  CertificationRevocation.certification_id == identifier)):
        raise business_error("Cette certification a deja sa revocation originale")
    row = CertificationRevocation(id=new_id("crv"), institute_id=institute, certification_id=identifier,
                                  **payload.model_dump(), actor_id=actor, created_at=utcnow())
    db.add(row)
    db.commit()
    db.refresh(row)
    return RevocationRead.model_validate(row)


def validity(record, now):
    if record.revocation:
        return "revoked"
    if record.valid_from > now:
        return "not_yet_valid"
    if record.valid_until is not None and record.valid_until <= now:
        return "expired"
    return "in_validity_window"


def list_records(db, institute, employee, limit=50, offset=0):
    lock_institute(db, institute)
    if not db.scalar(select(Employee.id).where(Employee.institute_id == institute, Employee.id == employee)):
        raise not_found("Collaboratrice introuvable")
    predicate = (EmployeeCertification.institute_id == institute, EmployeeCertification.employee_id == employee)
    total = db.scalar(select(func.count()).select_from(EmployeeCertification).where(*predicate))
    query = select(EmployeeCertification, CertificationRevocation).outerjoin(CertificationRevocation,
        (CertificationRevocation.institute_id == EmployeeCertification.institute_id)
        & (CertificationRevocation.certification_id == EmployeeCertification.id)
    ).where(*predicate).order_by(EmployeeCertification.valid_from, EmployeeCertification.id).limit(limit).offset(offset)
    now = utcnow()
    values = []
    for row, revocation in db.execute(query):
        result = CertificationRead.model_validate(row)
        result.revocation = RevocationRead.model_validate(revocation) if revocation else None
        values.append({"certificate": result, "state": validity(result, now)})
    return {"institute_id": institute, "employee_id": employee, "generated_at": now,
            "page": {"offset": offset, "limit": limit, "total": total}, "rows": values}
