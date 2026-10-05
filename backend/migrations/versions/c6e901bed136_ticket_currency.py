"""Invoice currency snapshots and explicit confirmation of unpaid legacy quotes."""
from alembic import op
import sqlalchemy as sa

revision = "c6e901bed136"
down_revision = "b5d890adc025"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("queue_tickets") as batch:
        batch.add_column(sa.Column("currency", sa.String(3), nullable=True))
        batch.create_check_constraint("ck_ticket_currency", "currency IS NULL OR currency IN ('CHF', 'EUR')")
    op.create_table("ticket_currency_facts",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("ticket_id", sa.String(80), sa.ForeignKey("queue_tickets.id"), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("ticket_id", name="uq_ticket_currency_fact"),
        sa.CheckConstraint("currency IN ('CHF', 'EUR')", name="ck_ticket_currency_fact"),
        sa.CheckConstraint("source IN ('institute_settings', 'cashier_confirmation')", name="ck_ticket_currency_source"))
    op.create_index("ix_ticket_currency_facts_institute_id", "ticket_currency_facts", ["institute_id"])


def downgrade():
    connection = op.get_bind()
    if (connection.execute(sa.text("SELECT id FROM queue_tickets WHERE currency IS NOT NULL LIMIT 1")).first()
            or connection.execute(sa.text("SELECT id FROM ticket_currency_facts LIMIT 1")).first()):
        raise RuntimeError("Ticket currency facts exist; downgrade cannot preserve invoice denomination")
    op.drop_table("ticket_currency_facts")
    with op.batch_alter_table("queue_tickets") as batch:
        batch.drop_constraint("ck_ticket_currency", type_="check")
        batch.drop_column("currency")
