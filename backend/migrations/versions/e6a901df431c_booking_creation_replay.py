"""Tenant-scoped booking creation replay.

Revision ID: e6a901df431c
Revises: d5f890ce320b
"""
from alembic import op
import sqlalchemy as sa

revision = "e6a901df431c"
down_revision = "d5f890ce320b"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("appointments") as batch:
        batch.add_column(sa.Column("idempotency_key", sa.String(120), nullable=True))
        batch.add_column(sa.Column("creation_fingerprint", sa.String(64), nullable=True))
        batch.create_unique_constraint("uq_appointment_institute_idempotency", ["institute_id", "idempotency_key"])


def downgrade():
    with op.batch_alter_table("appointments") as batch:
        batch.drop_constraint("uq_appointment_institute_idempotency", type_="unique")
        batch.drop_column("creation_fingerprint")
        batch.drop_column("idempotency_key")
