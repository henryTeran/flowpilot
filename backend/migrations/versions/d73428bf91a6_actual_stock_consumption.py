"""Actual signed service quantities in the existing exact stock ledger."""
from alembic import op
import sqlalchemy as sa
revision = "d73428bf91a6"
down_revision = "c62317ae80f5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("uq_stock_basis_owner", "stock_service_bases", ["institute_id", "id"], unique=True)
    op.create_table("stock_consumptions",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("basis_id", sa.String(80), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("institute_id", "id", name="uq_stock_consumption_owner"),
        sa.UniqueConstraint("basis_id", name="uq_stock_consumption_basis"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_stock_consumption_replay"),
        sa.ForeignKeyConstraint(["institute_id", "basis_id"], ["stock_service_bases.institute_id", "stock_service_bases.id"], name="fk_stock_consumption_basis_owner"))
    op.create_index("ix_stock_consumptions_institute_id", "stock_consumptions", ["institute_id"])
    with op.batch_alter_table("stock_movements") as batch:
        batch.add_column(sa.Column("consumption_id", sa.String(80)))
        batch.drop_constraint("ck_stock_movement_kind", type_="check")
        batch.create_check_constraint("ck_stock_movement_kind", "kind IN ('receipt','adjustment','consumption')")
        batch.create_check_constraint("ck_stock_consumption_movement", "(kind = 'consumption' AND consumption_id IS NOT NULL AND quantity_milli < 0) OR (kind != 'consumption' AND consumption_id IS NULL)")
        batch.create_unique_constraint("uq_stock_consumption_item", ["consumption_id", "item_id"])
        batch.create_foreign_key("fk_stock_movement_consumption_owner", "stock_consumptions", ["institute_id", "consumption_id"], ["institute_id", "id"])


def downgrade():
    connection = op.get_bind()
    if any(connection.execute(sa.text("SELECT id FROM " + table + " LIMIT 1")).first()
           for table in ("stock_consumptions", "stock_service_bases", "stock_recipes", "stock_items")):
        raise RuntimeError("Consumption or inventory exists; downgrade cannot preserve signed inventory history")
    with op.batch_alter_table("stock_movements") as batch:
        batch.drop_constraint("fk_stock_movement_consumption_owner", type_="foreignkey")
        batch.drop_constraint("uq_stock_consumption_item", type_="unique")
        batch.drop_constraint("ck_stock_consumption_movement", type_="check")
        batch.drop_constraint("ck_stock_movement_kind", type_="check")
        batch.drop_column("consumption_id")
        batch.create_check_constraint("ck_stock_movement_kind", "kind IN ('receipt','adjustment')")
    op.drop_table("stock_consumptions")
    op.drop_index("uq_stock_basis_owner", table_name="stock_service_bases")
