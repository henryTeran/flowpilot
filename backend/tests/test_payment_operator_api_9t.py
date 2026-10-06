from decimal import Decimal
from fastapi import HTTPException
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
import app.main as main_module
from app.main import app
from app.core.security import create_access_token
from app.modules.payments.registry import PaymentRegistry, payment_sessions
from app.modules.payments.dispatch import ProviderBinding
from app.modules.payments.models import PaymentIntent, PaymentExecution, WebhookReceipt
from app.modules.payments.provider import ProviderResult, ProviderStatus, VerifiedWebhook, PaymentAmount
from test_loyalty_earning_8r import setup
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers


class Adapter:
    def __init__(self):
        self.calls = []
        self.timeout = False
    def authorize(self, request):
        self.calls.append(("authorize", request))
        if self.timeout:
            raise TimeoutError("PRIVATE PROVIDER DETAILS")
        return ProviderResult("reference", ProviderStatus.AUTHORIZED, request.value)
    def capture(self, request, reference):
        self.calls.append(("capture", request))
        return ProviderResult(reference, ProviderStatus.CAPTURED, request.value)
    def cancel(self, request, reference):
        self.calls.append(("cancel", request))
        return ProviderResult(reference, ProviderStatus.CANCELLED, request.value)
    def refund(self, request, reference):
        self.calls.append(("refund", request))
        return ProviderResult(reference, ProviderStatus.REFUNDED, request.value)
    def webhook(self, event):
        # Explicit test simulation, not a real provider signature implementation.
        if event.headers.get("x-test-signature") != "test-authenticated" or event.body != b"original-provider-event":
            raise PermissionError("PRIVATE INVALID SIGNATURE")
        return VerifiedWebhook("test-event", ProviderResult("reference", ProviderStatus.AUTHORIZED,
                               PaymentAmount(Decimal("10.35"), "CHF")), "authorization")


@pytest.fixture
def flow(client):
    institute, employees, services = _bootstrap_reference_data(client)
    employee = employees[0]["id"]
    ticket, _, _ = setup(main_module.engine, institute, employee, services[0]["id"])
    adapter = Adapter()
    old = app.state.payment_registry
    app.state.payment_registry = PaymentRegistry([ProviderBinding(institute, "provider", "account", adapter)])
    app.dependency_overrides[payment_sessions] = lambda: sessionmaker(main_module.engine)
    try:
        yield client, institute, ticket, employee, adapter
    finally:
        app.state.payment_registry = old
        app.dependency_overrides.pop(payment_sessions, None)


def prepare(flow, kind="authorize", key="authorization", parent=None, amount="10.35", role="accueil"):
    client, institute, ticket, _, _ = flow
    return client.post(f"/api/v1/payments/institutes/{institute}/tickets/{ticket}/intents",
        headers=_auth_headers(role, institute), json=dict(kind=kind, amount=amount, currency="CHF",
                                                       idempotency_key=key, parent_intent_id=parent))


def dispatch(flow, identifier, role="accueil", headers=None):
    client, institute, _, _, _ = flow
    return client.post(f"/api/v1/payments/institutes/{institute}/intents/{identifier}/dispatch",
                       headers=headers or _auth_headers(role, institute))


def test_unconfigured_payments_refuse_without_preparing_or_dispatching(flow):
    _, institute, _, _, adapter = flow
    app.state.payment_registry = PaymentRegistry()
    assert prepare(flow).status_code == 503
    assert dispatch(flow, "missing").status_code == 503
    assert not adapter.calls
    with Session(main_module.engine) as db:
        assert list(db.scalars(select(PaymentIntent))) == []
    with pytest.raises(ValueError):
        binding = ProviderBinding(institute, "provider", "account", adapter)
        PaymentRegistry([binding, binding])


def test_unknown_dispatch_scope_original_identity_and_no_io_terminal_replay(flow):
    _, institute, _, _, adapter = flow
    first = prepare(flow)
    assert first.status_code == 200
    identifier = first.json()["id"]
    assert prepare(flow).json() == first.json()
    assert prepare(flow, amount="11.00").status_code == 400
    foreign = _auth_headers(institute_id="foreign")
    assert dispatch(flow, identifier, headers=foreign).status_code == 403
    other = create_access_token(subject="other", extra_claims={"role": "accueil", "institute_id": institute})
    assert dispatch(flow, identifier, headers={"Authorization": f"Bearer {other}"}).status_code == 403
    assert not adapter.calls
    correct_registry = app.state.payment_registry
    app.state.payment_registry = PaymentRegistry([ProviderBinding(institute, "provider", "other-account", adapter)])
    assert dispatch(flow, identifier).status_code == 400
    assert prepare(flow).status_code == 400
    assert not adapter.calls
    app.state.payment_registry = correct_registry
    adapter.timeout = True
    failed_transport = dispatch(flow, identifier)
    assert failed_transport.status_code == 503 and "PRIVATE" not in failed_transport.text
    with Session(main_module.engine) as db:
        assert db.get(PaymentExecution, identifier).released_at is None
    adapter.timeout = False
    confirmed = dispatch(flow, identifier)
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "authorized"
    assert dispatch(flow, identifier).json() == confirmed.json()
    assert len(adapter.calls) == 2
    assert adapter.calls[0][1] == adapter.calls[1][1]
    assert "provider_payment_id" not in confirmed.json()


def test_capture_application_and_manager_refund_use_server_parent_reference(flow):
    client, institute, ticket, employee, adapter = flow
    authorization = prepare(flow).json()["id"]
    assert dispatch(flow, authorization).status_code == 200
    assert prepare(flow, "capture", "wrong-parent", "foreign").status_code == 404
    capture = prepare(flow, "capture", "capture", authorization)
    assert capture.status_code == 200
    capture_id = capture.json()["id"]
    assert dispatch(flow, capture_id).json()["status"] == "captured"
    assert prepare(flow, "refund", "refund", capture_id, role="accueil").status_code == 403
    assert prepare(flow, "refund", "refund", capture_id, role="responsable_institut").status_code == 400
    checkout_path = f"/api/v1/payments/institutes/{institute}/intents/{capture_id}/checkout"
    closure = dict(employee_id=employee, method="cb")
    first = client.post(checkout_path, headers=_auth_headers(institute_id=institute), json=closure)
    assert first.status_code == 200 and first.json() == dict(ticket_id=ticket, status="paid")
    assert client.post(checkout_path, headers=_auth_headers(institute_id=institute), json=closure).json() == first.json()
    assert client.post(checkout_path, headers=_auth_headers(institute_id=institute), json={**closure, "method": "cheque"}).status_code == 400
    refund = prepare(flow, "refund", "refund", capture_id, amount="5.00", role="responsable_institut")
    assert refund.status_code == 200
    refund_id = refund.json()["id"]
    assert dispatch(flow, refund_id).status_code == 403
    result = dispatch(flow, refund_id, role="responsable_institut")
    assert result.status_code == 200 and result.json()["status"] == "refunded"
    assert dispatch(flow, refund_id, role="responsable_institut").json() == result.json()
    assert [kind for kind, _ in adapter.calls] == ["authorize", "capture", "refund"]
    assert adapter.calls[-1][1].value.amount == Decimal("5.00")


def test_cancel_releases_protection_and_request_cannot_inject_provider(flow):
    client, institute, ticket, _, adapter = flow
    path = f"/api/v1/payments/institutes/{institute}/tickets/{ticket}/intents"
    body = dict(kind="authorize", amount="10.35", currency="CHF", idempotency_key="authorization")
    for extra in ({"provider": "client-chosen"}, {"account_id": "foreign"}, {"actor_id": "manager"}, {"provider_payment_id": "foreign"}):
        assert client.post(path, headers=_auth_headers(institute_id=institute), json={**body, **extra}).status_code == 422
    assert prepare(flow, amount="10.351").status_code == 422
    authorization = prepare(flow).json()["id"]
    assert dispatch(flow, authorization).status_code == 200
    cancellation = prepare(flow, "cancel", "cancel", authorization).json()["id"]
    result = dispatch(flow, cancellation)
    assert result.status_code == 200 and result.json()["status"] == "cancelled"
    assert dispatch(flow, cancellation).json() == result.json()
    with Session(main_module.engine) as db:
        assert db.get(PaymentExecution, authorization).released_at is not None
    assert [kind for kind, _ in adapter.calls] == ["authorize", "cancel"]


def test_raw_webhook_authentication_recovery_and_receipt_replay(flow):
    client, institute, _, _, adapter = flow
    identifier = prepare(flow).json()["id"]
    adapter.timeout = True
    assert dispatch(flow, identifier).status_code == 503
    path = f"/api/v1/payments/institutes/{institute}/webhook"
    invalid = client.post(path, json={"verified": True})
    assert invalid.status_code == 400 and "PRIVATE" not in invalid.text
    assert client.post(path, content=b"x" * 65_537).status_code == 413
    with Session(main_module.engine) as db:
        assert list(db.scalars(select(WebhookReceipt))) == []
    headers = {"x-test-signature": "test-authenticated"}
    first = client.post(path, content=b"original-provider-event", headers=headers)
    assert first.status_code == 200 and first.json() == {"received": True}
    assert client.post(path, content=b"original-provider-event", headers=headers).json() == first.json()
    with Session(main_module.engine) as db:
        assert len(list(db.scalars(select(WebhookReceipt)))) == 1
    # Stored terminal outcome recovers without another transport call.
    assert dispatch(flow, identifier).json()["status"] == "authorized"
    assert len(adapter.calls) == 1


@pytest.mark.parametrize("kind", ["authorize", "capture", "cancel", "refund"])
def test_adapter_http_rejection_is_unknown_and_keeps_original_recovery(flow, kind, monkeypatch):
    client, institute, _, employee, adapter = flow
    authorization = prepare(flow).json()["id"]
    identifier, role = authorization, "accueil"
    if kind != "authorize":
        assert dispatch(flow, authorization).status_code == 200
        parent = authorization
        if kind == "refund":
            capture = prepare(flow, "capture", "capture", authorization).json()["id"]
            assert dispatch(flow, capture).status_code == 200
            path = f"/api/v1/payments/institutes/{institute}/intents/{capture}/checkout"
            assert client.post(path, headers=_auth_headers(institute_id=institute), json={"employee_id": employee, "method": "cb"}).status_code == 200
            parent, role = capture, "responsable_institut"
        identifier = prepare(flow, kind, kind, parent, role=role).json()["id"]
    original = getattr(adapter, kind)
    def http_error(*args):
        raise HTTPException(400, "PRIVATE PROVIDER REJECTION", headers={"x-private": "secret"})
    monkeypatch.setattr(adapter, kind, http_error)
    result = dispatch(flow, identifier, role=role)
    assert result.status_code == 503
    assert "PRIVATE" not in result.text and "x-private" not in result.headers
    snapshot = client.get(f"/api/v1/payments/institutes/{institute}/tickets/{flow[2]}/snapshot", headers=_auth_headers(institute_id=institute)).json()
    assert next(row for row in snapshot["operations"] if row["id"] == identifier)["status"] == "unknown"
    if kind != "refund":
        assert snapshot["protected"]
    else:
        assert prepare(flow, "refund", "competing-refund", parent, role=role).status_code == 400
    monkeypatch.setattr(adapter, kind, original)
    recovered = dispatch(flow, identifier, role=role)
    assert recovered.status_code == 200
    assert recovered.json()["status"] == {"authorize": "authorized", "capture": "captured", "cancel": "cancelled", "refund": "refunded"}[kind]


def test_adapter_webhook_http_error_cannot_escape_or_acknowledge_a_receipt(flow, monkeypatch):
    client, institute, _, _, adapter = flow
    authorization = prepare(flow).json()["id"]
    adapter.timeout = True
    assert dispatch(flow, authorization).status_code == 503
    original = adapter.webhook
    def http_error(event):
        raise HTTPException(401, "PRIVATE SIGNATURE DETAILS")
    monkeypatch.setattr(adapter, "webhook", http_error)
    path = f"/api/v1/payments/institutes/{institute}/webhook"
    result = client.post(path, content=b"original-provider-event", headers={"x-test-signature": "test-authenticated"})
    assert result.status_code == 503 and "PRIVATE" not in result.text
    with Session(main_module.engine) as db:
        assert list(db.scalars(select(WebhookReceipt))) == []
    monkeypatch.setattr(adapter, "webhook", original)
    assert client.post(path, content=b"original-provider-event", headers={"x-test-signature": "test-authenticated"}).json() == {"received": True}
