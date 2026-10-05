"""Explicit gift-card currency and replayable credited balances."""
from alembic import op
import sqlalchemy as sa

revision = "b5d890adc025"
down_revision = "a4c789fcb914"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("gift_card_settings",
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), primary_key=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.CheckConstraint("currency IN ('CHF', 'EUR')", name="ck_gift_card_currency"))
    op.create_table("gift_cards",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("initial_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("remaining", sa.Numeric(10, 2), nullable=False),
        sa.Column("valid_days", sa.Integer(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("customer_id", sa.String(80), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("issuance_reason", sa.String(240), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("creation_fingerprint", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_gift_card_issue_replay"),
        sa.UniqueConstraint("code", name="uq_gift_card_code"),
        sa.CheckConstraint("initial_amount > 0 AND remaining >= 0 AND remaining <= initial_amount", name="ck_gift_card_balance"),
        sa.CheckConstraint("valid_days > 0 AND expires_at > issued_at", name="ck_gift_card_validity"),
        sa.CheckConstraint("currency IN ('CHF', 'EUR')", name="ck_gift_card_issue_currency"))
    op.create_index("ix_gift_cards_institute_id", "gift_cards", ["institute_id"])
    op.create_index("ix_gift_cards_customer_id", "gift_cards", ["customer_id"])


def downgrade():
    for table in ("gift_cards", "gift_card_settings"):
        if op.get_bind().execute(sa.text(f"SELECT * FROM {table} LIMIT 1")).first():
            raise RuntimeError("Gift card records exist; downgrade cannot preserve currency/credit history")
    op.drop_table("gift_cards")
    op.drop_table("gift_card_settings")
