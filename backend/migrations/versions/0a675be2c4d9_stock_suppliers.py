"""Signed institute supplier identities; no manufactured catalogue."""
from alembic import op
import sqlalchemy as sa

revision = "0a675be2c4d9"
down_revision = "f9564ad1b3c8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("stock_suppliers",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("reference", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("institute_id", "id", name="uq_stock_supplier_owner"),
        sa.UniqueConstraint("institute_id", "reference", name="uq_stock_supplier_reference"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_stock_supplier_replay"))
    op.create_index("ix_stock_suppliers_institute_id", "stock_suppliers", ["institute_id"])


def downgrade():
    connection = op.get_bind()
    checks = (("SELECT id FROM stock_suppliers LIMIT 1", "Supplier identities exist; downgrade cannot preserve signed supplier history"),
        ("SELECT appointment_id FROM appointment_invoice_lines LIMIT 1", "Appointment invoice provenance exists; downgrade cannot preserve original invoice history"),
        ("SELECT id FROM ticket_lines WHERE invoice_removed_at IS NOT NULL LIMIT 1", "Invoice removals exist; downgrade cannot preserve signed correction history"))
    for query, message in checks:
        if connection.execute(sa.text(query)).first():
            raise RuntimeError(message)
    if any(connection.execute(sa.text("SELECT id FROM " + table + " LIMIT 1")).first()
           for table in ("stock_consumptions", "stock_service_bases", "stock_recipes", "stock_items")):
        raise RuntimeError("Inventory exists; downgrade cannot preserve signed inventory history")
    op.drop_table("stock_suppliers")
