import pytest
from sqlalchemy import select, event
from sqlalchemy.orm import Session, sessionmaker
from fastapi import HTTPException
import app.main as main_module
from app.modules.payments.dispatch import ProviderBinding
from app.modules.payments.provider import RawWebhook, VerifiedWebhook
from app.modules.payments.webhooks import receive_webhook
from app.modules.payments.models import WebhookReceipt, PaymentOutcome, PaymentExecution
from test_payment_outcomes_9f import prepare, result
from test_payment_dispatch_9g import Adapter
from test_ticket_workflow import _bootstrap_reference_data
from test_postgres_scheduling_4d import postgres_flow


class AuthenticatedAdapter(Adapter):
    def webhook(self, raw):
        if raw.headers.get("signature") != "test-signature":
            raise ValueError("Invalid test signature")
        return self.action


def binding(institute, status="failed", key="operation", event_id="event"):
    return ProviderBinding(institute, "provider", "account",
                           AuthenticatedAdapter(VerifiedWebhook(event_id, result(status), key)))


def test_webhook_authentication_correlation_replay_and_atomic_rollback(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    _, identifier = prepare(main_module.engine, institute, employees[0]["id"], services[0]["id"])
    sessions = sessionmaker(main_module.engine)
    raw = RawWebhook(b"sensitive-body", {"signature": "test-signature"})
    with pytest.raises(ValueError):
        receive_webhook(sessions, binding(institute), RawWebhook(b"body", {}))
    for configured in (binding(institute, key=None), binding(institute, key="missing"), binding("foreign")):
        with pytest.raises(HTTPException):
            receive_webhook(sessions, configured, raw)
    def fail(db, context, instances):
        if any(isinstance(row, WebhookReceipt) for row in db.new):
            raise RuntimeError("Injected receipt write failure")
    event.listen(Session, "before_flush", fail)
    try:
        with pytest.raises(RuntimeError):
            receive_webhook(sessions, binding(institute), raw)
    finally:
        event.remove(Session, "before_flush", fail)
    with Session(main_module.engine) as db:
        assert list(db.scalars(select(PaymentOutcome))) == []
        assert list(db.scalars(select(WebhookReceipt))) == []
        assert db.get(PaymentExecution, identifier).released_at is None
    first = receive_webhook(sessions, binding(institute), raw)
    assert receive_webhook(sessions, binding(institute), raw) == first
    with pytest.raises(HTTPException):
        receive_webhook(sessions, binding(institute, status="authorized"), raw)
    with Session(main_module.engine) as db:
        assert len(list(db.scalars(select(WebhookReceipt)))) == 1
        assert len(list(db.scalars(select(PaymentOutcome)))) == 1
        assert db.get(PaymentExecution, identifier).released_at is not None

    assert_webhook_downgrade_refused(main_module.engine, monkeypatch)

def test_concurrent_webhook_delivery_records_one_receipt_and_fact(postgres_flow, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    engine, institute, employee, care = postgres_flow
    _, identifier = prepare(engine, institute, employee, care)
    configured = binding(institute)
    raw = RawWebhook(b"body", {"signature": "test-signature"})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: receive_webhook(sessionmaker(engine), configured, raw), range(2)))
    assert results[0] == results[1]
    with Session(engine) as db:
        assert len(list(db.scalars(select(WebhookReceipt)))) == 1
        assert len(list(db.scalars(select(PaymentOutcome)))) == 1

    assert_webhook_downgrade_refused(engine, monkeypatch)

@pytest.mark.parametrize("kind,status,key", [("capture", "captured", "child"), ("cancel", "cancelled", "child"), ("refund", "refunded", "refund")])
def test_webhook_routes_exact_sealed_operation(client, kind, status, key):
    from app.modules.payments.provider import OperationKind
    from app.modules.payments.executions import seal_parent_operation
    from app.modules.payments.refunds import seal_refund
    from app.modules.payments.models import ParentOperationOutcome, RefundOutcome
    from test_payment_parent_execution_9i import child
    from test_refund_execution_9l import prepared
    institute, employees, services = _bootstrap_reference_data(client)
    employee, care = employees[0]["id"], services[0]["id"]
    if kind == "refund":
        _, identifier = prepared(main_module.engine, institute, employee, care)
        with Session(main_module.engine) as db:
            seal_refund(db, institute, identifier)
    else:
        _, _, identifier, _ = child(main_module.engine, institute, employee, care, OperationKind(kind))
        with Session(main_module.engine) as db:
            seal_parent_operation(db, institute, identifier)
    configured = binding(institute, status=status, key=key)
    receive_webhook(sessionmaker(main_module.engine), configured, RawWebhook(b"body", {"signature": "test-signature"}))
    with Session(main_module.engine) as db:
        receipt = db.get(WebhookReceipt, ("provider", "account", "event"))
        assert receipt.intent_id == identifier and receipt.status == status
        model = RefundOutcome if kind == "refund" else ParentOperationOutcome
        assert db.scalar(select(model).where(model.intent_id == identifier, model.status == status)) is not None


def assert_webhook_downgrade_refused(engine, monkeypatch):
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from app.core.config import settings
    from sqlalchemy import text
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
        command.stamp(config, "82ef237a9df1")
        with pytest.raises(RuntimeError, match="cannot preserve delivery history"):
            command.downgrade(config, "71de12698ce0")
