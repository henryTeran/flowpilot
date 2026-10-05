"""Retain package consumption history while permitting one active coverage per line."""
from alembic import op
import sqlalchemy as sa

revision = "c0e345b875d0"
down_revision = "b9d234a764cf"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("package_redemptions") as batch:
        batch.add_column(sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("reversed_by", sa.String(160), nullable=True))
        batch.add_column(sa.Column("reversal_reason", sa.String(200), nullable=True))
        batch.drop_constraint("uq_package_redeem_line", type_="unique")
        batch.create_check_constraint("ck_package_reversal_facts",
            "(reversed_at IS NULL AND reversed_by IS NULL AND reversal_reason IS NULL) OR "
            "(reversed_at IS NOT NULL AND reversal_reason IS NOT NULL AND reversed_at >= occurred_at)")
    op.create_index("uq_package_redeem_active_line", "package_redemptions", ["ticket_line_id"], unique=True,
                    sqlite_where=sa.text("reversed_at IS NULL"), postgresql_where=sa.text("reversed_at IS NULL"))


def downgrade():
    # Earlier schema cannot represent historical reapplications. Refuse rather
    # than silently discard a consumption record or change any balances.
    reversed_row = op.get_bind().execute(sa.text("SELECT id FROM package_redemptions WHERE reversed_at IS NOT NULL LIMIT 1")).first()
    if reversed_row is not None:
        raise RuntimeError("Package history contains reversals; downgrade cannot preserve it")
    op.drop_index("uq_package_redeem_active_line", table_name="package_redemptions")
    with op.batch_alter_table("package_redemptions") as batch:
        batch.drop_constraint("ck_package_reversal_facts", type_="check")
        batch.create_unique_constraint("uq_package_redeem_line", ["ticket_line_id"])
        batch.drop_column("reversal_reason")
        batch.drop_column("reversed_by")
        batch.drop_column("reversed_at")
