"""Immutable original appointment invoice line; no historical guessing."""
from alembic import op
import sqlalchemy as sa
revision = "f9564ad1b3c8"
down_revision = "e84539c0a2b7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("uq_queue_ticket_owner", "queue_tickets", ["institute_id", "id"], unique=True)
    op.create_index("uq_ticket_line_ticket_owner", "ticket_lines", ["ticket_id", "id"], unique=True)
    op.create_table("appointment_invoice_lines",
        sa.Column("appointment_id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("ticket_id", sa.String(80), nullable=False),
        sa.Column("ticket_line_id", sa.String(80), nullable=False),
        sa.Column("actor_id", sa.String(160)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["institute_id", "appointment_id"], ["appointments.institute_id", "appointments.id"], name="fk_appointment_invoice_source_owner"),
        sa.ForeignKeyConstraint(["institute_id", "ticket_id"], ["queue_tickets.institute_id", "queue_tickets.id"], name="fk_appointment_invoice_ticket_owner"),
        sa.ForeignKeyConstraint(["ticket_id", "ticket_line_id"], ["ticket_lines.ticket_id", "ticket_lines.id"], name="fk_appointment_invoice_line_owner"),
        sa.UniqueConstraint("ticket_id", name="uq_appointment_invoice_ticket"),
        sa.UniqueConstraint("ticket_line_id", name="uq_appointment_invoice_line"))
    op.create_index("ix_appointment_invoice_lines_institute_id", "appointment_invoice_lines", ["institute_id"])


def downgrade():
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT appointment_id FROM appointment_invoice_lines LIMIT 1")).first():
        raise RuntimeError("Appointment invoice provenance exists; downgrade cannot preserve original invoice history")
    if connection.execute(sa.text("SELECT id FROM ticket_lines WHERE invoice_removed_at IS NOT NULL LIMIT 1")).first():
        raise RuntimeError("Invoice removals exist; downgrade cannot preserve signed correction history")
    if any(connection.execute(sa.text("SELECT id FROM " + table + " LIMIT 1")).first()
           for table in ("stock_consumptions", "stock_service_bases", "stock_recipes", "stock_items")):
        raise RuntimeError("Inventory exists; downgrade cannot preserve signed inventory history")
    op.drop_table("appointment_invoice_lines")
    op.drop_index("uq_ticket_line_ticket_owner", table_name="ticket_lines")
    op.drop_index("uq_queue_ticket_owner", table_name="queue_tickets")
