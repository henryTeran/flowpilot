from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.employees.models import Employee
from app.modules.resources.repository import skill_facts
from app.modules.workforce import certifications
from app.modules.workforce.certification_schemas import CertificationCreate, CertificationRevoke, CertificationPage
from app.modules.workforce.models import EmployeeCertification, CertificationRevocation
from app.shared.time import utcnow
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def payload(employee, key="original"):
    now = utcnow()
    return {"employee_id": employee, "code": "CREDENTIAL", "title": "Recorded training", "issuer": "Declared issuer",
        "reference": "CRED-2026", "issued_on": (now-timedelta(days=2)).date().isoformat(),
        "valid_from": (now-timedelta(days=1)).isoformat(), "valid_until": (now+timedelta(days=1)).isoformat(),
        "reason": "Signed original declaration", "idempotency_key": key}


def test_original_certification_validity_replay_and_revocation_never_grant_skills(client, monkeypatch):
    institute, employee, _, path, headers = setup(client)
    with Session(main_module.engine) as db:
        original_skills = skill_facts(db, institute, [employee])
    body = payload(employee)
    reply = client.post(path + "/certifications", headers=headers, json=body)
    assert reply.status_code == 200, reply.text
    original = reply.json()
    assert original["actor_id"] == "test-user" and original["valid_from"].endswith("Z")
    assert client.post(path + "/certifications", headers=headers, json=body).json() == original
    assert client.get(path + "/certifications/original/original", headers=headers).json() == original
    assert client.get(path + "/certifications/original/missing", headers=headers).json() is None
    assert client.post(path + "/certifications", headers=headers, json={**body, "issuer": "Changed"}).status_code == 400
    read = lambda: CertificationPage.model_validate(client.get(f"{path}/employees/{employee}/certifications", headers=headers).json())
    assert read().rows[0].state == "in_validity_window"
    certificate = CertificationCreate.model_validate(body)
    with monkeypatch.context() as clock:
        clock.setattr(certifications, "utcnow", lambda: certificate.valid_from-timedelta(seconds=1))
        assert read().rows[0].state == "not_yet_valid"
        clock.setattr(certifications, "utcnow", lambda: certificate.valid_until)
        assert read().rows[0].state == "expired"  # Exact upper boundary is exclusive.
        assert client.post(path + "/certifications", headers=headers, json=body).json() == original
    revoke = {"reason": "Original document corrected", "idempotency_key": "revoke-original"}
    reply = client.post(f"{path}/certifications/{original['id']}/revoke", headers=headers, json=revoke)
    assert reply.status_code == 200, reply.text
    assert client.post(f"{path}/certifications/{original['id']}/revoke", headers=headers, json=revoke).json() == reply.json()
    assert client.get(path + "/certification-revocations/original/revoke-original", headers=headers).json() == reply.json()
    recovered = client.get(path + "/certifications/original/original", headers=headers).json()
    assert recovered["revocation"] == reply.json() and recovered["reference"] == original["reference"]
    assert client.post(f"{path}/certifications/{original['id']}/revoke", headers=headers,
        json={**revoke, "idempotency_key": "second"}).status_code == 400
    assert read().rows[0].state == "revoked"
    with Session(main_module.engine) as db:
        assert skill_facts(db, institute, [employee]) == original_skills
        assert len(list(db.scalars(select(EmployeeCertification)))) == 1
        assert len(list(db.scalars(select(CertificationRevocation)))) == 1


def test_certification_roles_ownership_required_nullable_dates_and_complete_pages(client):
    institute, employee, _, path, headers = setup(client)
    body = payload(employee)
    for role, tenant in [("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign"), ("responsable_institut", None)]:
        auth = _auth_headers(role, tenant)
        assert client.post(path + "/certifications", headers=auth, json=body).status_code == 403
        assert client.get(f"{path}/employees/{employee}/certifications", headers=auth).status_code == 403
    assert client.post(path + "/certifications", json=body).status_code == 403
    for changes in [{"valid_from": "2026-10-07T10:00:00"}, {"valid_until": body["valid_from"]}, {"actor_id": "forged"}, {"issuer": " "},
                    {"valid_from": "0001-01-01T00:00:00+14:00"}, {"valid_until": "9999-12-31T23:59:59-14:00"}]:
        assert client.post(path + "/certifications", headers=headers, json={**body, **changes}).status_code == 422
    assert client.post(path + "/certifications", headers=headers, json={key: value for key, value in body.items() if key != "valid_until"}).status_code == 422
    assert client.post(path + "/certifications", headers=headers, json={**body, "employee_id": "foreign"}).status_code == 404
    assert client.get(f"{path}/employees/foreign/certifications", headers=headers).status_code == 404
    assert client.get(f"{path}/employees/{employee}/certifications?limit=101", headers=headers).status_code == 422
    for index in range(2):
        assert client.post(path + "/certifications", headers=headers, json={**body, "issued_on": None,
            "valid_until": None, "idempotency_key": f"open-{index}"}).status_code == 200
    page = client.get(f"{path}/employees/{employee}/certifications?limit=1&offset=1", headers=headers).json()
    assert page["page"] == {"offset": 1, "limit": 1, "total": 2} and len(page["rows"]) == 1
    assert page["rows"][0]["certificate"]["valid_until"] is None and page["rows"][0]["certificate"]["issued_on"] is None


def test_actual_postgres_certification_original_race_actor_and_owner_constraints(postgres_flow):
    engine, institute, employee, _ = postgres_flow
    body = CertificationCreate.model_validate(payload(employee))
    barrier = Barrier(2)
    def create():
        with Session(engine) as db:
            barrier.wait(timeout=10)
            return certifications.create(db, institute, body, "signed").id
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(create) for _ in range(2)]
        ids = [future.result(timeout=20) for future in futures]
    assert ids[0] == ids[1]
    with Session(engine) as db:
        with pytest.raises(HTTPException):
            certifications.create(db, institute, body, "other-actor")
        db.rollback()
        db.add(EmployeeCertification(id="foreign", institute_id="foreign", **body.model_dump(), actor_id="signed", created_at=utcnow()))
        with pytest.raises(IntegrityError) as error:
            db.commit()
        assert error.value.orig.diag.constraint_name == "fk_certification_employee_owner"
        db.rollback()
        db.add(CertificationRevocation(id="foreign-revocation", institute_id="foreign", certification_id=ids[0],
            reason="Fixture", actor_id="signed", idempotency_key="foreign", created_at=utcnow()))
        with pytest.raises(IntegrityError) as error:
            db.commit()
        assert error.value.orig.diag.constraint_name == "fk_certification_revocation_owner"
        db.rollback()
        assert len(list(db.scalars(select(EmployeeCertification)))) == 1
