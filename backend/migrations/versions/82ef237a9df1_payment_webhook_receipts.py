"""Atomic account-scoped webhook receipts."""
from alembic import op
import sqlalchemy as sa
revision = "82ef237a9df1"
down_revision = "71de12698ce0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("payment_webhook_receipts",
        sa.Column("provider", sa.String(80), primary_key=True),
        sa.Column("account_id", sa.String(80), primary_key=True),
        sa.Column("event_id", sa.String(240), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("intent_id", sa.String(80), sa.ForeignKey("payment_intents.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider_payment_id", sa.String(240), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False))
    for field in ("institute_id", "intent_id"):
        op.create_index("ix_payment_webhook_receipts_" + field, "payment_webhook_receipts", [field])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT event_id FROM payment_webhook_receipts LIMIT 1")).first():
        raise RuntimeError("Webhook receipts exist; downgrade cannot preserve delivery history")
    op.drop_table("payment_webhook_receipts")
