"""Transactional stored-value allocations and gift/mixed closure facts."""
from alembic import op
import sqlalchemy as sa

revision = "d7fa12cfe247"
down_revision = "c6e901bed136"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("gift_card_allocations",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("card_id", sa.String(80), sa.ForeignKey("gift_cards.id"), nullable=False),
        sa.Column("ticket_id", sa.String(80), sa.ForeignKey("queue_tickets.id"), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_by", sa.String(160), nullable=True),
        sa.Column("reversal_reason", sa.String(240), nullable=True),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_gift_allocation_replay"),
        sa.CheckConstraint("amount > 0", name="ck_gift_allocation_amount"),
        sa.CheckConstraint("currency IN ('CHF', 'EUR')", name="ck_gift_allocation_currency"),
        sa.CheckConstraint("(reversed_at IS NULL AND reversed_by IS NULL AND reversal_reason IS NULL) OR (reversed_at IS NOT NULL AND reversed_by IS NOT NULL AND reversal_reason IS NOT NULL)", name="ck_gift_allocation_reversal"))
    for column in ("institute_id", "card_id", "ticket_id"):
        op.create_index(f"ix_gift_card_allocations_{column}", "gift_card_allocations", [column])
    op.create_table("gift_tender_closures",
        sa.Column("ticket_id", sa.String(80), sa.ForeignKey("queue_tickets.id"), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("gift_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("remainder_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("remainder_method", sa.String(16), nullable=True),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("gift_amount > 0 AND remainder_amount >= 0", name="ck_gift_closure_amount"),
        sa.CheckConstraint("currency IN ('CHF', 'EUR')", name="ck_gift_closure_currency"),
        sa.CheckConstraint("(remainder_amount = 0 AND remainder_method IS NULL) OR (remainder_amount > 0 AND remainder_method IS NOT NULL AND remainder_method IN ('cb', 'especes', 'cheque'))", name="ck_gift_closure_remainder"))
    op.create_index("ix_gift_tender_closures_institute_id", "gift_tender_closures", ["institute_id"])


def downgrade():
    connection = op.get_bind()
    for table in ("gift_card_allocations", "gift_tender_closures"):
        if connection.execute(sa.text(f"SELECT ticket_id FROM {table} LIMIT 1")).first():
            raise RuntimeError("Gift tender facts exist; downgrade cannot preserve payment history")
    op.drop_table("gift_tender_closures")
    op.drop_table("gift_card_allocations")
