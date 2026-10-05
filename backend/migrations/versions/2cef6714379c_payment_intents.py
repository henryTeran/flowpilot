"""Immutable scoped provider operation requests."""
from alembic import op
import sqlalchemy as sa
revision = "2cef6714379c"
down_revision = "1bde5603268b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("payment_intents",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("ticket_id", sa.String(80), sa.ForeignKey("queue_tickets.id"), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("account_id", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("provider_payment_id", sa.String(240), nullable=True),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_payment_intent_replay"),
        sa.CheckConstraint("kind IN ('authorize', 'capture', 'refund', 'cancel')", name="ck_payment_intent_kind"),
        sa.CheckConstraint("currency IN ('CHF', 'EUR') AND amount > 0", name="ck_payment_intent_value"),
        sa.CheckConstraint("kind = 'authorize' OR provider_payment_id IS NOT NULL", name="ck_payment_intent_reference"))
    for column in ("institute_id", "ticket_id"):
        op.create_index("ix_payment_intents_" + column, "payment_intents", [column])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT id FROM payment_intents LIMIT 1")).first():
        raise RuntimeError("Payment intents exist; downgrade cannot preserve original operation requests")
    op.drop_table("payment_intents")
