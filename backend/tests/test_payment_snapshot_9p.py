from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.payments.snapshots import ticket_payment_snapshot
from app.modules.payments.refunds import seal_refund, record_refund_outcome
from app.modules.payments.refund_loyalty import decide_refund_loyalty
from app.modules.payments.provider import ProviderResult, ProviderStatus
from test_refund_execution_9l import prepared
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def exercise(engine, institute, employee, care):
    ticket, refund = prepared(engine, institute, employee, care)
    with Session(engine) as db:
        snapshot = ticket_payment_snapshot(db, institute, ticket)
        assert not snapshot["protected"]
        assert next(row for row in snapshot["operations"] if row["id"] == refund)["status"] == "prepared"
        request = seal_refund(db, institute, refund)
        assert next(row for row in ticket_payment_snapshot(db, institute, ticket)["operations"] if row["id"] == refund)["status"] == "unknown"
        record_refund_outcome(db, institute, refund, "provider", "account", ProviderResult("reference", ProviderStatus.PENDING, request.value))
        assert next(row for row in ticket_payment_snapshot(db, institute, ticket)["operations"] if row["id"] == refund)["status"] == "pending"
        record_refund_outcome(db, institute, refund, "provider", "account", ProviderResult("reference", ProviderStatus.REFUNDED, request.value))
        decision = decide_refund_loyalty(db, institute, refund, -5, "Explicit correction", "decision", "manager")
        snapshot = ticket_payment_snapshot(db, institute, ticket)
        row = next(row for row in snapshot["operations"] if row["id"] == refund)
        assert row["status"] == "refunded" and row["loyalty_decision"].id == decision.id
        assert next(row for row in snapshot["operations"] if row["kind"] == "capture")["applied"]
    return ticket, refund


def test_ticket_payment_snapshot_recovery_and_jwt_scope(client):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, refund = exercise(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    path = f"/api/v1/payments/institutes/{institute}/tickets/{ticket}/snapshot"
    assert client.get(path, headers=_auth_headers(institute_id="foreign")).status_code == 403
    assert client.get(f"/api/v1/payments/institutes/{institute}/tickets/foreign/snapshot", headers=_auth_headers(institute_id=institute)).status_code == 404
    response = client.get(path, headers=_auth_headers(institute_id=institute))
    assert response.status_code == 200
    row = next(item for item in response.json()["operations"] if item["id"] == refund)
    assert row["amount"] == "10.35" and row["loyalty_decision"]["points"] == -5
    assert "provider_payment_id" not in row


def test_ticket_payment_snapshot_actual_postgresql(postgres_flow):
    exercise(*postgres_flow)


def test_unknown_authorization_retains_ticket_protection(client):
    from test_payment_outcomes_9f import prepare
    institute, employees, services = _bootstrap_reference_data(client)
    ticket, identifier = prepare(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    with Session(main_module.engine) as db:
        snapshot = ticket_payment_snapshot(db, institute, ticket)
        assert snapshot["protected"]
        row = next(row for row in snapshot["operations"] if row["id"] == identifier)
        assert row["status"] == "unknown" and row["active_protection"] and not row["applied"]
