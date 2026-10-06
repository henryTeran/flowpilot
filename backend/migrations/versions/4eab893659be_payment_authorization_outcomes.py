"""Immutable authorization outcomes and account-scoped references."""
from alembic import op
import sqlalchemy as sa
revision = "4eab893659be"
down_revision = "3dfa782548ad"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("payment_references",
        sa.Column("provider", sa.String(80), primary_key=True),
        sa.Column("account_id", sa.String(80), primary_key=True),
        sa.Column("provider_payment_id", sa.String(240), primary_key=True),
        sa.Column("intent_id", sa.String(80), sa.ForeignKey("payment_intents.id"), nullable=False, unique=True))
    op.create_table("payment_outcomes",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("intent_id", sa.String(80), sa.ForeignKey("payment_executions.intent_id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider_payment_id", sa.String(240), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("intent_id", "status", name="uq_payment_outcome_status"),
        sa.CheckConstraint("status IN ('pending', 'authorized', 'failed')", name="ck_payment_outcome_status"),
        sa.CheckConstraint("amount > 0 AND currency IN ('CHF', 'EUR')", name="ck_payment_outcome_value"))
    op.create_index("ix_payment_outcomes_intent_id", "payment_outcomes", ["intent_id"])


def downgrade():
    for table in ("payment_outcomes", "payment_references"):
        if op.get_bind().execute(sa.text("SELECT intent_id FROM " + table + " LIMIT 1")).first():
            raise RuntimeError("Payment outcomes exist; downgrade cannot preserve provider facts")
    op.drop_table("payment_outcomes")
    op.drop_table("payment_references")
