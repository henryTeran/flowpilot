from decimal import Decimal, localcontext
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.payments.ledger import cashflow_snapshot
from app.modules.payments.refunds import seal_refund, record_refund_outcome
from app.modules.payments.checkout import apply_capture
from app.modules.payments.provider import ProviderResult, ProviderStatus
from test_capture_checkout_9j import prepare
from test_refund_budget_9k import reserve
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def test_provider_cashflow_scoped_decimal_confirmed_and_reserved(client):
    institute, employees, services = _bootstrap_reference_data(client)
    employee = employees[0]["id"]
    ticket, _, capture = prepare(main_module.engine, institute, employee, services[0]["id"])
    with Session(main_module.engine) as db:
        first = cashflow_snapshot(db, institute)["accounts"][0]
        assert first["captured"] == Decimal("10.35") and first["unapplied"] == Decimal("10.35")
        apply_capture(db, institute, capture, employee, "operator", "cb")
        refund = reserve(db, institute, ticket, "refund", "3.00").id
        reserve(db, institute, ticket, "unknown", "2.00")
        request = seal_refund(db, institute, refund)
        record_refund_outcome(db, institute, refund, "provider", "account", ProviderResult("reference", ProviderStatus.REFUNDED, request.value))
        failed = reserve(db, institute, ticket, "failed", "1.00").id
        request = seal_refund(db, institute, failed)
        record_refund_outcome(db, institute, failed, "provider", "account", ProviderResult("reference", ProviderStatus.FAILED, request.value))
        with localcontext() as context:
            context.prec = 2
            row = cashflow_snapshot(db, institute)["accounts"][0]
        assert row == dict(provider="provider", account_id="account", currency="CHF", captured=Decimal("10.35"), applied=Decimal("10.35"), unapplied=Decimal("0.00"), refunded=Decimal("3.00"), refund_reserved=Decimal("2.00"), net_confirmed=Decimal("7.35"))
    path = f"/api/v1/payments/institutes/{institute}/cashflows"
    for headers in (_auth_headers(institute_id=institute), _auth_headers("responsable_institut", "foreign")):
        assert client.get(path, headers=headers).status_code == 403
    response = client.get(path, headers=_auth_headers("responsable_institut", institute))
    assert response.status_code == 200
    assert response.json()["accounts"][0]["net_confirmed"] == "7.35"


def test_persisted_cashflows_keep_currencies_and_accounts_separate(client):
    from app.modules.tickets.models import QueueTicket
    from app.modules.payments.models import PaymentIntent, PaymentExecution, ParentOperationExecution, ParentOperationOutcome
    from app.shared.time import utcnow
    institute, _, _ = _bootstrap_reference_data(client)
    with Session(main_module.engine) as db:
        assert cashflow_snapshot(db, institute)["accounts"] == []
        # Historical persisted units are read as recorded, without relabeling or FX.
        for suffix, currency, amount, account in (("chf", "CHF", "10.35", "account"), ("eur", "EUR", "20.10", "account"), ("second", "CHF", "3.25", "other-account")):
            ticket, auth, capture = "ticket-" + suffix, "auth-" + suffix, "capture-" + suffix
            db.add(QueueTicket(id=ticket, institute_id=institute, ticket_number=suffix, currency=currency, arrival_time=utcnow()))
            db.flush()
            terms = dict(institute_id=institute, ticket_id=ticket, provider="provider", account_id=account,
                         amount=Decimal(amount), currency=currency, actor_id="operator", created_at=utcnow())
            db.add(PaymentIntent(id=auth, kind="authorize", idempotency_key=auth, **terms))
            db.add(PaymentIntent(id=capture, kind="capture", idempotency_key=capture, provider_payment_id=suffix, **terms))
            db.flush()
            db.add(PaymentExecution(intent_id=auth, institute_id=institute, ticket_id=ticket, sealed_at=utcnow()))
            db.flush()
            db.add(ParentOperationExecution(intent_id=capture, parent_intent_id=auth, sealed_at=utcnow()))
            db.flush()
            db.add(ParentOperationOutcome(id="fact-" + suffix, intent_id=capture, status="captured",
                   provider_payment_id=suffix, amount=Decimal(amount), currency=currency, observed_at=utcnow()))
        db.commit()
        rows = cashflow_snapshot(db, institute)["accounts"]
        assert {(row["account_id"], row["currency"]): row["net_confirmed"] for row in rows} == {
            ("account", "CHF"): Decimal("10.35"), ("account", "EUR"): Decimal("20.10"), ("other-account", "CHF"): Decimal("3.25")}
        assert all(row["applied"] == 0 and row["unapplied"] == row["captured"] for row in rows)


def test_cashflow_snapshot_reads_actual_postgresql_facts(postgres_flow):
    engine, institute, employee, care = postgres_flow
    ticket, _, capture = prepare(engine, institute, employee, care)
    with Session(engine) as db:
        apply_capture(db, institute, capture, employee, "operator", "cb")
        identifier = reserve(db, institute, ticket, "refund", "5.00").id
        request = seal_refund(db, institute, identifier)
        record_refund_outcome(db, institute, identifier, "provider", "account",
                              ProviderResult("reference", ProviderStatus.REFUNDED, request.value))
    with Session(engine) as db:
        row = cashflow_snapshot(db, institute)["accounts"][0]
        assert row["net_confirmed"] == Decimal("5.35")
        assert row["applied"] == Decimal("10.35") and row["refund_reserved"] == 0
