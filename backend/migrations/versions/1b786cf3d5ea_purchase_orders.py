"""Immutable purchase orders and exact, linked partial receipts."""
from alembic import op
import sqlalchemy as sa
revision = "1b786cf3d5ea"
down_revision = "0a675be2c4d9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('stock_movements', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_stock_movement_item_owner', ['institute_id', 'item_id', 'id'])

    op.create_table('stock_purchase_orders',
    sa.Column('id', sa.String(length=80), nullable=False),
    sa.Column('institute_id', sa.String(length=80), nullable=False),
    sa.Column('supplier_id', sa.String(length=80), nullable=False),
    sa.Column('supplier_reference', sa.String(length=80), nullable=False),
    sa.Column('supplier_name', sa.String(length=120), nullable=False),
    sa.Column('reference', sa.String(length=80), nullable=False),
    sa.Column('reason', sa.String(length=240), nullable=False),
    sa.Column('actor_id', sa.String(length=160), nullable=False),
    sa.Column('idempotency_key', sa.String(length=120), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['institute_id', 'supplier_id'], ['stock_suppliers.institute_id', 'stock_suppliers.id'], name='fk_stock_order_supplier_owner'),
    sa.ForeignKeyConstraint(['institute_id'], ['institutes.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('institute_id', 'id', name='uq_stock_order_owner'),
    sa.UniqueConstraint('institute_id', 'idempotency_key', name='uq_stock_order_replay'),
    sa.UniqueConstraint('institute_id', 'reference', name='uq_stock_order_reference')
    )
    with op.batch_alter_table('stock_purchase_orders', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_stock_purchase_orders_institute_id'), ['institute_id'], unique=False)

    op.create_table('stock_purchase_order_lines',
    sa.Column('order_id', sa.String(length=80), nullable=False),
    sa.Column('item_id', sa.String(length=80), nullable=False),
    sa.Column('institute_id', sa.String(length=80), nullable=False),
    sa.Column('item_name', sa.String(length=120), nullable=False),
    sa.Column('item_sku', sa.String(length=80), nullable=False),
    sa.Column('unit', sa.String(length=10), nullable=False),
    sa.Column('quantity_milli', sa.BigInteger(), nullable=False),
    sa.CheckConstraint("unit IN ('ml','g','unit') AND (unit != 'unit' OR quantity_milli % 1000 = 0)", name='ck_stock_order_line_unit'),
    sa.CheckConstraint('quantity_milli BETWEEN 1 AND 999999999999999', name='ck_stock_order_line_quantity'),
    sa.ForeignKeyConstraint(['institute_id', 'item_id'], ['stock_items.institute_id', 'stock_items.id'], name='fk_stock_order_line_item'),
    sa.ForeignKeyConstraint(['institute_id', 'order_id'], ['stock_purchase_orders.institute_id', 'stock_purchase_orders.id'], name='fk_stock_order_line_owner'),
    sa.PrimaryKeyConstraint('order_id', 'item_id'),
    sa.UniqueConstraint('institute_id', 'order_id', 'item_id', 'unit', name='uq_stock_order_line_owner')
    )
    with op.batch_alter_table('stock_purchase_order_lines', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_stock_purchase_order_lines_institute_id'), ['institute_id'], unique=False)

    op.create_table('stock_purchase_receipts',
    sa.Column('id', sa.String(length=80), nullable=False),
    sa.Column('institute_id', sa.String(length=80), nullable=False),
    sa.Column('order_id', sa.String(length=80), nullable=False),
    sa.Column('reason', sa.String(length=240), nullable=False),
    sa.Column('actor_id', sa.String(length=160), nullable=False),
    sa.Column('idempotency_key', sa.String(length=120), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['institute_id', 'order_id'], ['stock_purchase_orders.institute_id', 'stock_purchase_orders.id'], name='fk_stock_purchase_receipt_order'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('institute_id', 'idempotency_key', name='uq_stock_purchase_receipt_replay'),
    sa.UniqueConstraint('institute_id', 'order_id', 'id', name='uq_stock_purchase_receipt_owner')
    )
    with op.batch_alter_table('stock_purchase_receipts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_stock_purchase_receipts_institute_id'), ['institute_id'], unique=False)

    op.create_table('stock_purchase_receipt_lines',
    sa.Column('receipt_id', sa.String(length=80), nullable=False),
    sa.Column('item_id', sa.String(length=80), nullable=False),
    sa.Column('institute_id', sa.String(length=80), nullable=False),
    sa.Column('order_id', sa.String(length=80), nullable=False),
    sa.Column('unit', sa.String(length=10), nullable=False),
    sa.Column('quantity_milli', sa.BigInteger(), nullable=False),
    sa.Column('movement_id', sa.String(length=80), nullable=False),
    sa.CheckConstraint("unit IN ('ml','g','unit') AND (unit != 'unit' OR quantity_milli % 1000 = 0)", name='ck_stock_purchase_receipt_unit'),
    sa.CheckConstraint('quantity_milli BETWEEN 1 AND 999999999999999', name='ck_stock_purchase_receipt_quantity'),
    sa.ForeignKeyConstraint(['institute_id', 'item_id', 'movement_id'], ['stock_movements.institute_id', 'stock_movements.item_id', 'stock_movements.id'], name='fk_stock_purchase_receipt_movement'),
    sa.ForeignKeyConstraint(['institute_id', 'order_id', 'item_id', 'unit'], ['stock_purchase_order_lines.institute_id', 'stock_purchase_order_lines.order_id', 'stock_purchase_order_lines.item_id', 'stock_purchase_order_lines.unit'], name='fk_stock_purchase_receipt_order_line'),
    sa.ForeignKeyConstraint(['institute_id', 'order_id', 'receipt_id'], ['stock_purchase_receipts.institute_id', 'stock_purchase_receipts.order_id', 'stock_purchase_receipts.id'], name='fk_stock_purchase_receipt_line_owner'),
    sa.PrimaryKeyConstraint('receipt_id', 'item_id'),
    sa.UniqueConstraint('movement_id', name='uq_stock_purchase_receipt_movement')
    )
    with op.batch_alter_table('stock_purchase_receipt_lines', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_stock_purchase_receipt_lines_institute_id'), ['institute_id'], unique=False)
        batch_op.create_index('ix_stock_purchase_receipt_line_order', ['institute_id', 'order_id', 'item_id'], unique=False)



def downgrade():
    connection = op.get_bind()
    checks = (("SELECT id FROM stock_purchase_orders LIMIT 1", "Purchase orders exist; downgrade cannot preserve signed purchase history"),
        ("SELECT id FROM stock_suppliers LIMIT 1", "Supplier identities exist; downgrade cannot preserve signed supplier history"),
        ("SELECT appointment_id FROM appointment_invoice_lines LIMIT 1", "Appointment invoice provenance exists; downgrade cannot preserve original invoice history"),
        ("SELECT id FROM ticket_lines WHERE invoice_removed_at IS NOT NULL LIMIT 1", "Invoice removals exist; downgrade cannot preserve signed correction history"))
    for query, message in checks:
        if connection.execute(sa.text(query)).first():
            raise RuntimeError(message)
    if any(connection.execute(sa.text("SELECT id FROM " + table + " LIMIT 1")).first()
           for table in ("stock_consumptions", "stock_service_bases", "stock_recipes", "stock_items")):
        raise RuntimeError("Inventory exists; downgrade cannot preserve signed inventory history")
    op.drop_table("stock_purchase_receipt_lines")
    op.drop_table("stock_purchase_receipts")
    op.drop_table("stock_purchase_order_lines")
    op.drop_table("stock_purchase_orders")
    with op.batch_alter_table("stock_movements") as batch_op:
        batch_op.drop_constraint("uq_stock_movement_item_owner", type_="unique")
