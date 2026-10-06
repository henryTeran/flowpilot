"""Signed refund loyalty decisions linked to point entries."""
from alembic import op
import sqlalchemy as sa
revision = "93f0348baef2"
down_revision = "82ef237a9df1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("payment_refund_loyalty_decisions",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("refund_intent_id", sa.String(80), sa.ForeignKey("payment_refund_executions.intent_id"), nullable=False, unique=True),
        sa.Column("ticket_id", sa.String(80), sa.ForeignKey("queue_tickets.id"), nullable=False),
        sa.Column("customer_id", sa.String(80), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("entry_id", sa.String(80), sa.ForeignKey("loyalty_entries.id"), nullable=True, unique=True),
        sa.Column("points", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_refund_loyalty_replay"),
        sa.CheckConstraint("points <= 0", name="ck_refund_loyalty_points"),
        sa.CheckConstraint("(points = 0 AND entry_id IS NULL) OR (points < 0 AND entry_id IS NOT NULL AND customer_id IS NOT NULL)", name="ck_refund_loyalty_entry"))
    for field in ("institute_id", "ticket_id"):
        op.create_index("ix_payment_refund_loyalty_decisions_" + field, "payment_refund_loyalty_decisions", [field])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT id FROM payment_refund_loyalty_decisions LIMIT 1")).first():
        raise RuntimeError("Refund loyalty decisions exist; downgrade cannot preserve signed history")
    op.drop_table("payment_refund_loyalty_decisions")
