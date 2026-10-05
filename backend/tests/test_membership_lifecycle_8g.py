from datetime import timedelta
from pathlib import Path
from threading import Barrier
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.customers.schemas import CustomerCreate
from app.modules.customers.service import create_customer
from app.modules.memberships import service
from app.modules.memberships.models import CustomerMembership, MembershipPlan, MembershipRenewal
from app.modules.memberships.schemas import MembershipIssue, MembershipRenew, PlanCreate
from app.shared.exceptions import business_error
from app.shared.time import utcnow
from app.core.security import create_access_token
from test_postgres_scheduling_4d import postgres_flow, race
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def prepare(engine, institute):
    with Session(engine) as db:
        customer = create_customer(db, institute, CustomerCreate(display_name="Member client", idempotency_key="member-client"), "creator")
        plan = service.create_plan(db, institute, PlanCreate(name="Monthly rights", valid_days=30, idempotency_key="member-plan"), "manager")
        return customer.id, plan.id


def test_membership_scope_replay_snapshot_and_renewal_boundaries(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    customer, plan = prepare(main_module.engine, institute)
    manager = _auth_headers("responsable_institut", institute)
    reception = _auth_headers(institute_id=institute)
    prefix = f"/api/v1/memberships/institutes/{institute}"
    now = utcnow()
    monkeypatch.setattr(service, "utcnow", lambda: now)
    terms = {"name": "Monthly rights", "valid_days": 30, "idempotency_key": "member-plan"}
    unidentified = create_access_token(subject="", extra_claims={"role": "responsable_institut", "institute_id": institute})
    assert client.post(prefix + "/plans", headers={"Authorization": f"Bearer {unidentified}"}, json=terms).status_code == 403
    assert client.post(prefix + "/plans", headers=reception, json=terms).status_code == 403
    assert client.post(prefix + "/plans", headers=manager, json=terms).json()["id"] == plan
    assert client.post(prefix + "/plans", headers=manager, json={**terms, "valid_days": 40}).status_code == 400
    assert client.post(prefix + "/plans", headers=manager, json={**terms, "valid_days": True}).status_code == 422
    assert client.get(prefix + "/plans", headers=_auth_headers("responsable_institut", None)).status_code == 403
    assert client.get(prefix + "/plans", headers=reception).status_code == 200
    payload = {"plan_id": plan, "customer_id": customer, "idempotency_key": "member-issue"}
    assert client.post(prefix, headers=reception, json=payload).status_code == 403
    assert client.post(prefix, headers=_auth_headers("responsable_institut", "foreign"), json=payload).status_code == 403
    assert client.post(prefix, headers=manager, json={**payload, "customer_id": "customer_missing"}).status_code == 404
    first = client.post(prefix, headers=manager, json=payload)
    assert first.status_code == 200, first.text
    row = first.json()
    assert row["status"] == "active" and row["valid_days"] == 30
    assert client.post(prefix, headers=manager, json=payload).json() == row
    assert client.post(prefix, headers=manager, json={**payload, "customer_id": "customer_missing"}).status_code == 400
    assert client.post(prefix, headers=manager, json={**payload, "idempotency_key": "other-issue"}).status_code == 400
    with Session(main_module.engine) as db:
        origin = db.get(CustomerMembership, row["id"])
        original_until = service.aware(origin.active_until)
        db.get(MembershipPlan, plan).valid_days = 50
        db.commit()
    path = prefix + f"/{row['id']}/renew"
    renewal_payload = {"idempotency_key": "member-renew"}
    assert client.post(path, headers=reception, json=renewal_payload).status_code == 403
    renewal = client.post(path, headers=manager, json=renewal_payload)
    assert renewal.status_code == 200, renewal.text
    assert client.post(path, headers=manager, json=renewal_payload).json() == renewal.json()
    with Session(main_module.engine) as db:
        active = db.get(CustomerMembership, row["id"])
        assert service.aware(active.active_until) == original_until + timedelta(days=30)
        assert service.aware(active.active_from) == now
        assert service.membership_view(active, now - timedelta(microseconds=1))["status"] == "scheduled"
        assert service.membership_view(active, service.aware(active.active_until))["status"] == "expired"
        assert service.membership_view(active, service.aware(active.active_until) - timedelta(microseconds=1))["status"] == "active"
        extended_until = service.aware(active.active_until)
    after_gap = extended_until + timedelta(days=3)
    monkeypatch.setattr(service, "utcnow", lambda: after_gap)
    renewed = client.post(path, headers=manager, json={"idempotency_key": "restart-after-gap"})
    assert renewed.status_code == 200, renewed.text
    with Session(main_module.engine) as db:
        active = db.get(CustomerMembership, row["id"])
        assert service.aware(active.active_from) == after_gap
        assert service.aware(active.active_until) == after_gap + timedelta(days=30)
        assert active.actor_id == "test-user"
        facts = db.scalars(select(MembershipRenewal).order_by(MembershipRenewal.active_until)).all()
        assert len(facts) == 2 and all(item.actor_id == "test-user" for item in facts)
    assert len(client.get(prefix + f"/{row['id']}/history", headers=reception).json()) == 2
    assert client.post(path, headers=manager, json=renewal_payload).json() == renewal.json()
    assert client.post(prefix, headers=manager, json=payload).json()["active_from"] == renewed.json()["active_from"]
    next_period = after_gap + timedelta(days=31)
    monkeypatch.setattr(service, "utcnow", lambda: next_period)
    replacement = client.post(prefix, headers=manager, json={**payload, "idempotency_key": "replacement-membership"})
    assert replacement.status_code == 200, replacement.text
    replacement_id = replacement.json()["id"]
    assert client.post(path, headers=manager, json={"idempotency_key": "old-membership-restart"}).status_code == 400
    assert client.post(prefix + f"/{replacement_id}/renew", headers=manager, json=renewal_payload).status_code == 400
    assert client.get(prefix + f"/{row['id']}/history", headers=_auth_headers("accueil", "foreign")).status_code == 403
    assert_downgrade_preserves_memberships(main_module.engine, monkeypatch)


def test_renewal_flush_failure_rolls_back_window_and_history(client):
    institute, employees, services = _bootstrap_reference_data(client)
    customer, plan = prepare(main_module.engine, institute)
    with Session(main_module.engine) as db:
        membership = service.issue_membership(db, institute, MembershipIssue(plan_id=plan,
            customer_id=customer, idempotency_key="rollback-issue"), "manager")
        identifier, before = membership.id, service.aware(membership.active_until)
    def fail(db, context, instances):
        if any(isinstance(row, MembershipRenewal) for row in db.new):
            raise business_error("Injected renewal failure")
    event.listen(Session, "before_flush", fail)
    try:
        response = client.post(f"/api/v1/memberships/institutes/{institute}/{identifier}/renew",
            headers=_auth_headers("responsable_institut", institute), json={"idempotency_key": "rollback-renew"})
        assert response.status_code == 400
    finally:
        event.remove(Session, "before_flush", fail)
    with Session(main_module.engine) as db:
        assert service.aware(db.get(CustomerMembership, identifier).active_until) == before
        assert len(db.scalars(select(MembershipRenewal)).all()) == 0


@pytest.mark.parametrize("same_intent", [True, False])
def test_concurrent_membership_issue_cannot_duplicate_active_rights(postgres_flow, same_intent):
    engine, institute, employee, care = postgres_flow
    customer, plan = prepare(engine, institute)
    results = race(engine, [lambda db: service.issue_membership(db, institute,
        MembershipIssue(plan_id=plan, customer_id=customer, idempotency_key="issue-a"), "manager"),
        lambda db: service.issue_membership(db, institute, MembershipIssue(plan_id=plan, customer_id=customer,
            idempotency_key="issue-a" if same_intent else "issue-b"), "manager")])
    assert [status for status, _ in results].count("ok") == (2 if same_intent else 1)
    if same_intent:
        assert results[0] == results[1]
    with Session(engine) as db:
        assert len(db.scalars(select(CustomerMembership)).all()) == 1


@pytest.mark.parametrize("same_intent", [True, False])
def test_renewals_preserve_replay_and_preloaded_expiry(postgres_flow, monkeypatch, same_intent):
    engine, institute, employee, care = postgres_flow
    customer, plan = prepare(engine, institute)
    with Session(engine) as db:
        row = service.issue_membership(db, institute, MembershipIssue(plan_id=plan,
            customer_id=customer, idempotency_key="renew-issue"), "manager")
        identifier, before = row.id, service.aware(row.active_until)
    preloaded = Barrier(2)
    def renew(db, key):
        # Both transactions cache the original expiry before either mutation.
        db.get(CustomerMembership, identifier)
        preloaded.wait(timeout=10)
        return service.renew_membership(db, institute, identifier, MembershipRenew(idempotency_key=key), "manager")
    results = race(engine, [lambda db: renew(db, "renew-a"),
                           lambda db: renew(db, "renew-a" if same_intent else "renew-b")])
    assert all(status == "ok" for status, _ in results)
    assert (results[0] == results[1]) == same_intent
    with Session(engine) as db:
        count = 1 if same_intent else 2
        assert service.aware(db.get(CustomerMembership, identifier).active_until) == before + timedelta(days=30 * count)
        assert len(db.scalars(select(MembershipRenewal)).all()) == count
    assert_downgrade_preserves_memberships(engine, monkeypatch)


def test_expired_renewal_and_replacement_issue_cannot_overlap(postgres_flow, monkeypatch):
    engine, institute, employee, care = postgres_flow
    customer, plan = prepare(engine, institute)
    with Session(engine) as db:
        old = service.issue_membership(db, institute, MembershipIssue(plan_id=plan,
            customer_id=customer, idempotency_key="expiring-member"), "manager")
        identifier, until = old.id, service.aware(old.active_until)
    monkeypatch.setattr(service, "utcnow", lambda: until + timedelta(days=1))
    results = race(engine, [lambda db: service.renew_membership(db, institute, identifier,
        MembershipRenew(idempotency_key="restart-member"), "manager"), lambda db: service.issue_membership(db, institute,
        MembershipIssue(plan_id=plan, customer_id=customer, idempotency_key="replacement-member"), "manager")])
    assert sorted(status for status, _ in results) == ["conflict", "ok"]
    with Session(engine) as db:
        members = db.scalars(select(CustomerMembership)).all()
        assert sum(service.membership_view(row)["status"] == "active" for row in members) == 1


def assert_downgrade_preserves_memberships(engine, monkeypatch):
    from app.core.config import settings
    url = engine.url
    if engine.dialect.name == "postgresql":
        with engine.connect() as connection:
            schema = connection.scalar(text("SELECT current_schema()"))
        assert schema.startswith("fp_test_")
        url = url.update_query_dict({"options": f"-csearch_path={schema}"})
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    with monkeypatch.context() as patch:
        patch.setattr(settings, "DATABASE_URL", url.render_as_string(hide_password=False))
        command.stamp(config, "f3b678eba803")
        with pytest.raises(RuntimeError, match="cannot preserve"):
            command.downgrade(config, "e2a567da97f2")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "f3b678eba803"
