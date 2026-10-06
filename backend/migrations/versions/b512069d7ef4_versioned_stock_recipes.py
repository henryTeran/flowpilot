"""Immutable institute-scoped per-service stock recipes."""
from alembic import op
import sqlalchemy as sa
revision = "b512069d7ef4"
down_revision = "a401958c6de3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("stock_recipes",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("service_id", sa.String(80), sa.ForeignKey("services.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("institute_id", "id", name="uq_stock_recipe_owner"),
        sa.UniqueConstraint("institute_id", "service_id", "revision", name="uq_stock_recipe_revision"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_stock_recipe_replay"),
        sa.CheckConstraint("revision BETWEEN 1 AND 1000000000", name="ck_stock_recipe_revision"))
    for field in ("institute_id", "service_id"):
        op.create_index("ix_stock_recipes_" + field, "stock_recipes", [field])
    op.create_table("stock_recipe_lines",
        sa.Column("recipe_id", sa.String(80), primary_key=True),
        sa.Column("item_id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), nullable=False),
        sa.Column("quantity_milli", sa.BigInteger(), nullable=False),
        sa.Column("unit", sa.String(10), nullable=False),
        sa.ForeignKeyConstraint(["institute_id", "recipe_id"], ["stock_recipes.institute_id", "stock_recipes.id"], name="fk_stock_recipe_line_owner"),
        sa.ForeignKeyConstraint(["institute_id", "item_id"], ["stock_items.institute_id", "stock_items.id"], name="fk_stock_recipe_line_item"),
        sa.CheckConstraint("quantity_milli BETWEEN 1 AND 999999999999999", name="ck_stock_recipe_line_quantity"),
        sa.CheckConstraint("unit IN ('ml','g','unit')", name="ck_stock_recipe_line_unit"),
        sa.CheckConstraint("unit != 'unit' OR quantity_milli % 1000 = 0", name="ck_stock_recipe_line_whole"))
    op.create_index("ix_stock_recipe_lines_institute_id", "stock_recipe_lines", ["institute_id"])


def downgrade():
    # Fail before DDL, including an attempted downgrade past the stock ledger.
    # SQLite does not roll back every DDL operation if a lower guard refuses.
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT id FROM stock_recipes LIMIT 1")).first() or connection.execute(sa.text("SELECT id FROM stock_items LIMIT 1")).first():
        raise RuntimeError("Inventory catalogue or recipes exist; downgrade cannot preserve signed inventory history")
    op.drop_table("stock_recipe_lines")
    op.drop_table("stock_recipes")
