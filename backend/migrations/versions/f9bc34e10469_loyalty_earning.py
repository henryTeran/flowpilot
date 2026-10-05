"""Immutable earning-policy revisions and paid-checkout earning snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "f9bc34e10469"
down_revision = "e8ab23d0f358"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("loyalty_earning_policies",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("points_per_unit", sa.Numeric(9, 4), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_loyalty_policy_replay"),
        sa.UniqueConstraint("institute_id", "revision", name="uq_loyalty_policy_revision"),
        sa.CheckConstraint("currency IN ('CHF', 'EUR')", name="ck_loyalty_policy_currency"),
        sa.CheckConstraint("points_per_unit > 0 AND points_per_unit <= 10000 AND revision > 0", name="ck_loyalty_policy_rate"))
    op.create_index("ix_loyalty_earning_policies_institute_id", "loyalty_earning_policies", ["institute_id"])
    op.create_table("loyalty_earnings",
        sa.Column("ticket_id", sa.String(80), sa.ForeignKey("queue_tickets.id"), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("customer_id", sa.String(80), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("policy_id", sa.String(80), sa.ForeignKey("loyalty_earning_policies.id"), nullable=False),
        sa.Column("entry_id", sa.String(80), sa.ForeignKey("loyalty_entries.id"), nullable=True, unique=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("basis_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("points_per_unit", sa.Numeric(9, 4), nullable=False),
        sa.Column("points", sa.BigInteger(), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("currency IN ('CHF', 'EUR')", name="ck_loyalty_earning_currency"),
        sa.CheckConstraint("basis_amount >= 0 AND points >= 0 AND points_per_unit > 0", name="ck_loyalty_earning_amount"),
        sa.CheckConstraint("(points = 0 AND entry_id IS NULL) OR (points > 0 AND entry_id IS NOT NULL)", name="ck_loyalty_earning_entry"))
    op.create_index("ix_loyalty_earnings_institute_id", "loyalty_earnings", ["institute_id"])
    op.create_index("ix_loyalty_earnings_customer_id", "loyalty_earnings", ["customer_id"])


def downgrade():
    connection = op.get_bind()
    for table, key in (("loyalty_earnings", "ticket_id"), ("loyalty_earning_policies", "id")):
        if connection.execute(sa.text(f"SELECT {key} FROM {table} LIMIT 1")).first():
            raise RuntimeError("Loyalty earning facts exist; downgrade cannot preserve policy or checkout history")
    op.drop_table("loyalty_earnings")
    op.drop_table("loyalty_earning_policies")
