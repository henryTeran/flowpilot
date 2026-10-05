"""Transactional loyalty spending and reversal price snapshots."""
from alembic import op
import sqlalchemy as sa
revision = "1bde5603268b"
down_revision = "0acd45f2157a"
branch_labels = None
depends_on = None


def upgrade():
    columns = [sa.Column("id", sa.String(80), primary_key=True)]
    for name, target in (("institute_id", "institutes.id"), ("customer_id", "customers.id"),
                         ("reward_id", "loyalty_rewards.id"), ("ticket_line_id", "ticket_lines.id"),
                         ("entry_id", "loyalty_entries.id")):
        columns.append(sa.Column(name, sa.String(80), sa.ForeignKey(target), nullable=False))
    columns.extend([sa.Column("quantity", sa.Integer(), nullable=False),
                    sa.Column("points_cost", sa.BigInteger(), nullable=False),
                    sa.Column("currency", sa.String(3), nullable=False)])
    for name in ("original_unit_price", "original_total", "reward_unit_price", "reward_total"):
        columns.append(sa.Column(name, sa.Numeric(10, 2), nullable=False))
    columns.extend([sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reversal_entry_id", sa.String(80), sa.ForeignKey("loyalty_entries.id"), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_by", sa.String(160), nullable=True),
        sa.Column("reversal_reason", sa.String(240), nullable=True),
        sa.UniqueConstraint("entry_id"), sa.UniqueConstraint("reversal_entry_id"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_loyalty_redemption_replay"),
        sa.CheckConstraint("quantity > 0 AND points_cost > 0", name="ck_loyalty_redemption_points"),
        sa.CheckConstraint("currency IN ('CHF', 'EUR')", name="ck_loyalty_redemption_currency"),
        sa.CheckConstraint("original_unit_price > reward_unit_price AND reward_unit_price >= 0 AND original_total > reward_total AND reward_total >= 0", name="ck_loyalty_redemption_prices"),
        sa.CheckConstraint("(reversed_at IS NULL AND reversal_entry_id IS NULL AND reversed_by IS NULL AND reversal_reason IS NULL) OR (reversed_at IS NOT NULL AND reversal_entry_id IS NOT NULL AND reversed_by IS NOT NULL AND reversal_reason IS NOT NULL AND reversed_at >= occurred_at)", name="ck_loyalty_redemption_reversal")])
    op.create_table("loyalty_redemptions", *columns)
    for name in ("institute_id", "customer_id"):
        op.create_index("ix_loyalty_redemptions_" + name, "loyalty_redemptions", [name])
    op.create_index("uq_loyalty_redemption_active_line", "loyalty_redemptions", ["ticket_line_id"], unique=True,
                    sqlite_where=sa.text("reversed_at IS NULL"), postgresql_where=sa.text("reversed_at IS NULL"))


def downgrade():
    if op.get_bind().execute(sa.text("SELECT id FROM loyalty_redemptions LIMIT 1")).first():
        raise RuntimeError("Loyalty redemptions exist; downgrade cannot preserve spending history")
    op.drop_table("loyalty_redemptions")
