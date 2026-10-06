"""Durable capture/cancel dispatch seals linked to authorization."""
from alembic import op
import sqlalchemy as sa
revision = "5fbc90476acf"
down_revision = "4eab893659be"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("payment_parent_executions",
        sa.Column("intent_id", sa.String(80), sa.ForeignKey("payment_intents.id"), primary_key=True),
        sa.Column("parent_intent_id", sa.String(80), sa.ForeignKey("payment_executions.intent_id"), nullable=False),
        sa.Column("sealed_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_payment_parent_executions_parent_intent_id", "payment_parent_executions", ["parent_intent_id"])

    op.create_table("payment_parent_outcomes",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("intent_id", sa.String(80), sa.ForeignKey("payment_parent_executions.intent_id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider_payment_id", sa.String(240), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("intent_id", "status", name="uq_payment_parent_outcome_status"),
        sa.CheckConstraint("status IN ('pending', 'failed', 'captured', 'cancelled')", name="ck_payment_parent_outcome_status"),
        sa.CheckConstraint("amount > 0 AND currency IN ('CHF', 'EUR')", name="ck_payment_parent_outcome_value"))
    op.create_index("ix_payment_parent_outcomes_intent_id", "payment_parent_outcomes", ["intent_id"])


def downgrade():
    for table in ("payment_parent_outcomes", "payment_parent_executions"):
        if op.get_bind().execute(sa.text("SELECT intent_id FROM " + table + " LIMIT 1")).first():
            raise RuntimeError("Parent payment executions exist; downgrade cannot preserve dispatch seals")
    op.drop_table("payment_parent_outcomes")
    op.drop_table("payment_parent_executions")
