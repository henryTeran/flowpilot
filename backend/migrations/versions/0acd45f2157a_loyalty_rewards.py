"""Explicit immutable service reward terms."""
from alembic import op
import sqlalchemy as sa
revision = "0acd45f2157a"
down_revision = "f9bc34e10469"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("loyalty_rewards",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("service_id", sa.String(80), sa.ForeignKey("services.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("points_cost", sa.BigInteger(), nullable=False),
        sa.Column("minimum_points", sa.BigInteger(), nullable=False),
        sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_loyalty_reward_replay"),
        sa.CheckConstraint("points_cost > 0 AND minimum_points >= 0", name="ck_loyalty_reward_points"),
        sa.CheckConstraint("discount_amount > 0", name="ck_loyalty_reward_amount"),
        sa.CheckConstraint("currency IN ('CHF', 'EUR')", name="ck_loyalty_reward_currency"))
    op.create_index("ix_loyalty_rewards_institute_id", "loyalty_rewards", ["institute_id"])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT id FROM loyalty_rewards LIMIT 1")).first():
        raise RuntimeError("Loyalty rewards exist; downgrade cannot preserve reward terms")
    op.drop_table("loyalty_rewards")
