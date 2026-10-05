"""Scoped loyalty point history and explicit balance-based tiers."""
from alembic import op
import sqlalchemy as sa

revision = "e8ab23d0f358"
down_revision = "d7fa12cfe247"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("loyalty_entries",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("customer_id", sa.String(80), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("points", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_loyalty_entry_replay"),
        sa.CheckConstraint("points <> 0", name="ck_loyalty_entry_points"))
    op.create_index("ix_loyalty_entries_institute_id", "loyalty_entries", ["institute_id"])
    op.create_index("ix_loyalty_entries_customer_id", "loyalty_entries", ["customer_id"])
    op.create_table("loyalty_tiers",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("minimum_points", sa.BigInteger(), nullable=False),
        sa.Column("benefit_description", sa.String(240), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_loyalty_tier_replay"),
        sa.UniqueConstraint("institute_id", "minimum_points", name="uq_loyalty_tier_threshold"),
        sa.CheckConstraint("minimum_points >= 0", name="ck_loyalty_tier_threshold"))
    op.create_index("ix_loyalty_tiers_institute_id", "loyalty_tiers", ["institute_id"])


def downgrade():
    connection = op.get_bind()
    for table in ("loyalty_entries", "loyalty_tiers"):
        if connection.execute(sa.text(f"SELECT id FROM {table} LIMIT 1")).first():
            raise RuntimeError("Loyalty facts exist; downgrade cannot preserve point history or configured tiers")
    op.drop_table("loyalty_tiers")
    op.drop_table("loyalty_entries")
