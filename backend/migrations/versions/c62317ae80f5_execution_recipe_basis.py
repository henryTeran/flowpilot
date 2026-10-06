"""Pin immutable recipe identity at actual service execution start."""
from alembic import op
import sqlalchemy as sa
revision = "c62317ae80f5"
down_revision = "b512069d7ef4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("uq_service_session_owner", "service_sessions", ["institute_id", "id"], unique=True)
    op.create_index("uq_appointment_owner", "appointments", ["institute_id", "id"], unique=True)
    op.create_table("stock_service_bases",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("session_id", sa.String(80)),
        sa.Column("ticket_line_id", sa.String(80), sa.ForeignKey("ticket_lines.id")),
        sa.Column("appointment_id", sa.String(80)),
        sa.Column("service_id", sa.String(80), sa.ForeignKey("services.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.String(80)),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(160)),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["institute_id", "recipe_id"], ["stock_recipes.institute_id", "stock_recipes.id"], name="fk_stock_basis_recipe_owner"),
        sa.ForeignKeyConstraint(["institute_id", "session_id"], ["service_sessions.institute_id", "service_sessions.id"], name="fk_stock_basis_session_owner"),
        sa.ForeignKeyConstraint(["institute_id", "appointment_id"], ["appointments.institute_id", "appointments.id"], name="fk_stock_basis_appointment_owner"),
        sa.UniqueConstraint("session_id", "ticket_line_id", name="uq_stock_basis_session_line"),
        sa.UniqueConstraint("appointment_id", name="uq_stock_basis_appointment"),
        sa.CheckConstraint("(session_id IS NOT NULL AND ticket_line_id IS NOT NULL AND appointment_id IS NULL) OR (session_id IS NULL AND ticket_line_id IS NULL AND appointment_id IS NOT NULL)", name="ck_stock_basis_source"),
        sa.CheckConstraint("quantity > 0", name="ck_stock_basis_quantity"),
        sa.CheckConstraint("(state = 'unconfigured' AND recipe_id IS NULL) OR (state IN ('enabled','disabled') AND recipe_id IS NOT NULL)", name="ck_stock_basis_configuration"))
    op.create_index("ix_stock_service_bases_institute_id", "stock_service_bases", ["institute_id"])


def downgrade():
    # Refuse before DDL if this or an earlier inventory guard would lose facts.
    connection = op.get_bind()
    if any(connection.execute(sa.text("SELECT id FROM " + table + " LIMIT 1")).first()
           for table in ("stock_service_bases", "stock_recipes", "stock_items")):
        raise RuntimeError("Execution or inventory exists; downgrade cannot preserve signed inventory history")
    op.drop_table("stock_service_bases")
    op.drop_index("uq_appointment_owner", table_name="appointments")
    op.drop_index("uq_service_session_owner", table_name="service_sessions")
