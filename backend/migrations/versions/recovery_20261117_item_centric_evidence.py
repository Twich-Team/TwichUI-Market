"""Add item recovery decisions and honest per-request evidence. No backfill."""
from alembic import op
import sqlalchemy as sa
revision = 'recovery_20261117'
down_revision = 'usability_20261117'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_metadata_sources_recent','metadata_sources',['provider','retrieved_at'])
    op.add_column('metadata_sources', sa.Column('recovery_json', sa.Text(), nullable=True))
    op.add_column('metadata_tasks', sa.Column('decision_json', sa.Text(), nullable=True))
    op.add_column('metadata_tasks', sa.Column('force_refresh', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table('metadata_attempts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('metadata_tasks.id'), nullable=True),
        sa.Column('provider', sa.String(24), nullable=False),
        sa.Column('region', sa.String(2), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=True),
        sa.Column('kind', sa.String(24), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('state', sa.String(16), nullable=False),
        sa.Column('http_status', sa.Integer(), nullable=True),
        sa.Column('outcome', sa.String(32), nullable=True),
        sa.Column('decision_json', sa.Text(), nullable=True),
        sa.Column('returned_json', sa.Text(), nullable=True),
        sa.Column('new_json', sa.Text(), nullable=True),
        sa.Column('updated_json', sa.Text(), nullable=True))
    op.create_table('metadata_recovery_items',sa.Column('region',sa.String(2),primary_key=True),sa.Column('item_id',sa.Integer(),primary_key=True),sa.Column('locale',sa.String(8),primary_key=True),sa.Column('status',sa.String(24),nullable=False),sa.Column('decided_at',sa.DateTime(timezone=True),nullable=False),sa.Column('next_at',sa.DateTime(timezone=True)),sa.Column('decision_json',sa.Text(),nullable=False))
    op.create_table('metadata_recovery_state',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('turn',sa.Integer(),nullable=False),sa.Column('historical_after',sa.DateTime(timezone=True)),sa.Column('audit_after',sa.DateTime(timezone=True)))
    op.create_index('ix_metadata_attempts_period', 'metadata_attempts', ['started_at','provider'])
    op.create_index('ix_metadata_attempts_item', 'metadata_attempts', ['region','item_id','started_at'])


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS(SELECT 1 FROM metadata_recovery_items) OR EXISTS(SELECT 1 FROM metadata_attempts) OR EXISTS(SELECT 1 FROM metadata_tasks WHERE decision_json IS NOT NULL) OR EXISTS(SELECT 1 FROM metadata_sources WHERE recovery_json IS NOT NULL)')):
        raise RuntimeError('Retain recovery evidence; use compatible image rollback without schema downgrade')
    op.drop_table('metadata_recovery_items')
    op.drop_table('metadata_recovery_state')
    op.drop_table('metadata_attempts')
    op.drop_column('metadata_tasks', 'force_refresh')
    op.drop_column('metadata_tasks', 'decision_json')
    op.drop_column('metadata_sources', 'recovery_json')
    op.drop_index('ix_metadata_sources_recent',table_name='metadata_sources')
