"""Refund execution and immutable outcomes."""
from alembic import op
import sqlalchemy as sa
revision = "71de12698ce0"
down_revision = "60cd01587bdf"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("payment_refund_executions",
        sa.Column("intent_id", sa.String(80), sa.ForeignKey("payment_intents.id"), primary_key=True),
        sa.Column("capture_intent_id", sa.String(80), sa.ForeignKey("payment_parent_executions.intent_id"), nullable=False),
        sa.Column("sealed_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_payment_refund_executions_capture_intent_id", "payment_refund_executions", ["capture_intent_id"])
    op.create_table("payment_refund_outcomes",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("intent_id", sa.String(80), sa.ForeignKey("payment_refund_executions.intent_id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider_payment_id", sa.String(240), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("intent_id", "status", name="uq_payment_refund_outcome_status"),
        sa.CheckConstraint("status IN ('pending', 'failed', 'refunded')", name="ck_payment_refund_outcome_status"),
        sa.CheckConstraint("amount > 0 AND currency IN ('CHF', 'EUR')", name="ck_payment_refund_outcome_value"))
    op.create_index("ix_payment_refund_outcomes_intent_id", "payment_refund_outcomes", ["intent_id"])


def downgrade():
    for table in ("payment_refund_outcomes", "payment_refund_executions"):
        if op.get_bind().execute(sa.text("SELECT intent_id FROM " + table + " LIMIT 1")).first():
            raise RuntimeError("Refund history exists; downgrade cannot preserve provider facts")
    op.drop_table("payment_refund_outcomes")
    op.drop_table("payment_refund_executions")
