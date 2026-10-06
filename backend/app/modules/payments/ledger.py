"""Confirmed provider cash flows; service revenue and gifted credit are separate."""
from decimal import Decimal, localcontext
from sqlalchemy import select
from app.modules.payments.models import PaymentIntent, ParentOperationOutcome, RefundOutcome, CaptureApplication
from app.modules.tickets.repository import lock_institute


def cashflow_snapshot(db, institute_id):
    lock_institute(db, institute_id)
    groups = {}
    def group(intent):
        key = (intent.provider, intent.account_id, intent.currency)
        if key not in groups:
            groups[key] = dict(provider=key[0], account_id=key[1], currency=key[2],
                captured=Decimal("0.00"), applied=Decimal("0.00"), refunded=Decimal("0.00"),
                refund_reserved=Decimal("0.00"))
        return groups[key]
    captures = db.execute(select(PaymentIntent, ParentOperationOutcome.amount).join(
        ParentOperationOutcome, ParentOperationOutcome.intent_id == PaymentIntent.id).where(
        PaymentIntent.institute_id == institute_id, PaymentIntent.kind == "capture",
        ParentOperationOutcome.status == "captured")).all()
    applied = set(db.scalars(select(CaptureApplication.intent_id).where(CaptureApplication.institute_id == institute_id)))
    refunds = list(db.scalars(select(PaymentIntent).where(
        PaymentIntent.institute_id == institute_id, PaymentIntent.kind == "refund")))
    statuses = dict(db.execute(select(RefundOutcome.intent_id, RefundOutcome.status).join(
        PaymentIntent, PaymentIntent.id == RefundOutcome.intent_id).where(
        PaymentIntent.institute_id == institute_id, RefundOutcome.status != "pending")).all())
    with localcontext() as context:
        context.prec = 28
        for intent, amount in captures:
            row = group(intent)
            row["captured"] += amount
            if intent.id in applied:
                row["applied"] += amount
        for intent in refunds:
            status = statuses.get(intent.id)
            if status == "failed":
                continue
            row = group(intent)
            row["refunded" if status == "refunded" else "refund_reserved"] += intent.amount
        for row in groups.values():
            row["unapplied"] = row["captured"] - row["applied"]
            row["net_confirmed"] = row["captured"] - row["refunded"]
    return dict(institute_id=institute_id, accounts=[groups[key] for key in sorted(groups)])
