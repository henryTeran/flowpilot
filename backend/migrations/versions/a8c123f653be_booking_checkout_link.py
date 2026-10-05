"""Durable booking-to-checkout handoff; legacy bookings remain unlinked."""
from alembic import op
import sqlalchemy as sa

revision = "a8c123f653be"
down_revision = "f7b012e542ad"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("appointments") as batch:
        batch.add_column(sa.Column("checkout_ticket_id", sa.String(80), nullable=True))
        batch.create_foreign_key("fk_appointment_checkout_ticket", "queue_tickets", ["checkout_ticket_id"], ["id"])
        batch.create_unique_constraint("uq_appointment_checkout_ticket", ["checkout_ticket_id"])


def downgrade():
    with op.batch_alter_table("appointments") as batch:
        batch.drop_constraint("uq_appointment_checkout_ticket", type_="unique")
        batch.drop_constraint("fk_appointment_checkout_ticket", type_="foreignkey")
        batch.drop_column("checkout_ticket_id")
