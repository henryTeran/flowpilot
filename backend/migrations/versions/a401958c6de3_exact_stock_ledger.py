"""Institute-scoped exact stock catalogue and signed movement ledger."""
from alembic import op
import sqlalchemy as sa

revision = "a401958c6de3"
down_revision = "93f0348baef2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("stock_items",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("sku", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("unit", sa.String(10), nullable=False),
        sa.Column("reorder_milli", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("institute_id", "id", name="uq_stock_item_owner"),
        sa.UniqueConstraint("institute_id", "sku", name="uq_stock_item_sku"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_stock_item_replay"),
        sa.CheckConstraint("category IN ('retail','cabine','consumable')", name="ck_stock_item_category"),
        sa.CheckConstraint("unit IN ('ml','g','unit')", name="ck_stock_item_unit"),
        sa.CheckConstraint("reorder_milli >= 0 AND reorder_milli <= 999999999999999", name="ck_stock_item_threshold"),
        sa.CheckConstraint("unit != 'unit' OR reorder_milli % 1000 = 0", name="ck_stock_item_whole_threshold"))
    op.create_index("ix_stock_items_institute_id", "stock_items", ["institute_id"])
    op.create_table("stock_movements",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("item_id", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("quantity_milli", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["institute_id", "item_id"], ["stock_items.institute_id", "stock_items.id"], name="fk_stock_movement_owner"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_stock_movement_replay"),
        sa.CheckConstraint("kind IN ('receipt','adjustment')", name="ck_stock_movement_kind"),
        sa.CheckConstraint("quantity_milli != 0 AND quantity_milli BETWEEN -999999999999999 AND 999999999999999", name="ck_stock_movement_quantity"),
        sa.CheckConstraint("kind != 'receipt' OR quantity_milli > 0", name="ck_stock_receipt_positive"))
    for field in ("institute_id", "item_id"):
        op.create_index("ix_stock_movements_" + field, "stock_movements", [field])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT id FROM stock_items LIMIT 1")).first():
        raise RuntimeError("Stock catalogue exists; downgrade cannot preserve signed inventory history")
    op.drop_table("stock_movements")
    op.drop_table("stock_items")
