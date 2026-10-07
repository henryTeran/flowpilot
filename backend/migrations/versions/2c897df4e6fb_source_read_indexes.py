"""Scoped operational source indexes; no history rewrite or backfill."""
from alembic import op

revision = "2c897df4e6fb"
down_revision = "1b786cf3d5ea"
branch_labels = None
depends_on = None

INDEXES = (
    ("ix_appointment_inst_status_actual_end", "appointments", ["institute_id", "status", "actual_end_time"]),
    ("ix_appointment_inst_status_slot", "appointments", ["institute_id", "status", "start_time", "end_time"]),
    ("ix_session_inst_status_real_end", "service_sessions", ["institute_id", "status", "real_end_time"]),
    ("ix_queue_ticket_inst_status", "queue_tickets", ["institute_id", "status"]),
)


def upgrade():
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns, unique=False)


def downgrade():
    for name, table, _columns in reversed(INDEXES):
        op.drop_index(name, table_name=table)
