"""Recorded member pricing with reversible, nonstacking checkout coverage."""
from alembic import op
import sqlalchemy as sa

revision = "a4c789fcb914"
down_revision = "f3b678eba803"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("membership_benefits",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("membership_id", sa.String(80), sa.ForeignKey("customer_memberships.id"), nullable=False),
        sa.Column("ticket_line_id", sa.String(80), sa.ForeignKey("ticket_lines.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        *[sa.Column(name, sa.Numeric(10, 2), nullable=False) for name in
          ("original_unit_price", "original_total", "member_unit_price", "member_total")],
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_by", sa.String(160), nullable=True),
        sa.Column("reversal_reason", sa.String(240), nullable=True),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_membership_benefit_replay"),
        sa.CheckConstraint("quantity > 0 AND original_unit_price >= 0 AND original_total >= 0 AND "
            "member_unit_price >= 0 AND member_total >= 0 AND member_unit_price < original_unit_price "
            "AND member_total < original_total", name="ck_membership_benefit_prices"),
        sa.CheckConstraint("(reversed_at IS NULL AND reversed_by IS NULL AND reversal_reason IS NULL) OR "
            "(reversed_at IS NOT NULL AND reversal_reason IS NOT NULL AND reversed_at >= occurred_at)",
            name="ck_membership_benefit_reversal"))
    op.create_index("ix_membership_benefits_institute_id", "membership_benefits", ["institute_id"])
    op.create_index("ix_membership_benefits_membership_id", "membership_benefits", ["membership_id"])
    op.create_index("uq_membership_benefit_active_line", "membership_benefits", ["ticket_line_id"], unique=True,
                    sqlite_where=sa.text("reversed_at IS NULL"), postgresql_where=sa.text("reversed_at IS NULL"))


def downgrade():
    if op.get_bind().execute(sa.text("SELECT id FROM membership_benefits LIMIT 1")).first():
        raise RuntimeError("Membership benefits exist; downgrade cannot preserve checkout pricing history")
    op.drop_table("membership_benefits")
