"""Retain execution provenance when removing an unpaid invoice line."""
from alembic import op
import sqlalchemy as sa
revision = "e84539c0a2b7"
down_revision = "d73428bf91a6"
branch_labels = None
depends_on = None
CHECK = "(invoice_removed_at IS NULL AND invoice_removed_by_actor IS NULL AND invoice_removal_reason IS NULL) OR (invoice_removed_at IS NOT NULL AND invoice_removed_by_actor IS NOT NULL AND length(trim(invoice_removed_by_actor)) > 0 AND invoice_removal_reason IS NOT NULL AND invoice_removal_reason = 'not_performed')"

def upgrade():
    with op.batch_alter_table("ticket_lines") as batch:
        batch.add_column(sa.Column("invoice_removed_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("invoice_removed_by_actor", sa.String(160)))
        batch.add_column(sa.Column("invoice_removal_reason", sa.String(32)))
        batch.create_check_constraint("ck_ticket_line_invoice_removal", CHECK)

def downgrade():
    if op.get_bind().execute(sa.text("SELECT id FROM ticket_lines WHERE invoice_removed_at IS NOT NULL LIMIT 1")).first():
        raise RuntimeError("Invoice removals exist; downgrade cannot preserve signed correction history")
    if any(op.get_bind().execute(sa.text("SELECT id FROM " + table + " LIMIT 1")).first()
           for table in ("stock_consumptions", "stock_service_bases", "stock_recipes", "stock_items")):
        raise RuntimeError("Inventory exists; downgrade cannot preserve signed inventory history")
    with op.batch_alter_table("ticket_lines") as batch:
        batch.drop_constraint("ck_ticket_line_invoice_removal", type_="check")
        batch.drop_column("invoice_removal_reason")
        batch.drop_column("invoice_removed_by_actor")
        batch.drop_column("invoice_removed_at")
