"""Scoped lifecycle event captures, revisions and heads."""
from alembic import context, op
import sqlalchemy as sa
revision = "fb6c8de54037"
down_revision = "ea5b7cd43926"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('crm_event_capture_originals',
        sa.Column('id', sa.String(80), primary_key=True),
        sa.Column('institute_id', sa.String(80), sa.ForeignKey('institutes.id'), nullable=False),
        sa.Column('customer_id', sa.String(80), sa.ForeignKey('customers.id'), nullable=False),
        sa.Column('idempotency_key', sa.String(120), nullable=False),
        sa.Column('actor_id', sa.String(160), nullable=False),
        sa.Column('reason', sa.String(240), nullable=False),
        sa.Column('captured_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source', sa.JSON, nullable=False),
        sa.UniqueConstraint('institute_id', 'customer_id', 'id', name='uq_crm_event_capture_owner'),
        sa.UniqueConstraint('institute_id', 'customer_id', 'idempotency_key', name='uq_crm_event_capture_replay'))

    op.create_table('crm_event_revisions',
        sa.Column('id', sa.String(80), primary_key=True),
        sa.Column('institute_id', sa.String(80), sa.ForeignKey('institutes.id'), nullable=False),
        sa.Column('customer_id', sa.String(80), sa.ForeignKey('customers.id'), nullable=False),
        sa.Column('event_key', sa.String(80), nullable=False),
        sa.Column('capture_id', sa.String(80), nullable=False),
        sa.Column('previous_id', sa.String(80), nullable=True),
        sa.Column('decision', sa.JSON, nullable=False),
        sa.UniqueConstraint('institute_id', 'customer_id', 'event_key', 'id', name='uq_crm_event_revision_owner'),
        sa.ForeignKeyConstraint(['institute_id', 'customer_id', 'capture_id'], ['crm_event_capture_originals.institute_id', 'crm_event_capture_originals.customer_id', 'crm_event_capture_originals.id'], name='fk_crm_event_revision_capture_owner'),
        sa.ForeignKeyConstraint(['institute_id', 'customer_id', 'event_key', 'previous_id'], ['crm_event_revisions.institute_id', 'crm_event_revisions.customer_id', 'crm_event_revisions.event_key', 'crm_event_revisions.id'], name='fk_crm_event_revision_previous_owner'))

    op.create_table('crm_event_heads',
        sa.Column('institute_id', sa.String(80), sa.ForeignKey('institutes.id'), primary_key=True),
        sa.Column('customer_id', sa.String(80), sa.ForeignKey('customers.id'), primary_key=True),
        sa.Column('event_key', sa.String(80), primary_key=True),
        sa.Column('revision_id', sa.String(80), nullable=False),
        sa.ForeignKeyConstraint(['institute_id', 'customer_id', 'event_key', 'revision_id'], ['crm_event_revisions.institute_id', 'crm_event_revisions.customer_id', 'crm_event_revisions.event_key', 'crm_event_revisions.id'], name='fk_crm_event_head_owner'))

def downgrade():
    if context.is_offline_mode(): raise RuntimeError("Event history verification requires online downgrade")
    tables = ("crm_event_heads", "crm_event_revisions", "crm_event_capture_originals")
    if any(op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() for table in tables):
        raise RuntimeError("Recorded event history cannot be removed by downgrade")
    for table in tables: op.drop_table(table)
