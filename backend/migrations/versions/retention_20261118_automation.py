"""Add inactive automatic retention state and durable execution receipts."""
from alembic import op
import sqlalchemy as sa

revision = 'retention_20261118'
down_revision = 'coverage_20261117'
branch_labels = depends_on = None


def upgrade():
    for name in ('retention_eligible_rows','retention_processed_rows','filesystem_available_bytes'):
        op.add_column('storage_measurements',sa.Column(name,sa.BigInteger()))
    op.create_table('retention_automation',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('authorization', sa.Text()),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('authorized_at', sa.DateTime(timezone=True)),
        sa.Column('next_run_at', sa.DateTime(timezone=True)))
    op.create_table('retention_executions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
        sa.Column('policy_hash', sa.String(64), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('reason', sa.String(200)),
        sa.Column('batches', sa.Integer(), nullable=False),
        sa.Column('rows_processed', sa.Integer(), nullable=False),
        sa.Column('progress', sa.Text(), nullable=False))
    op.create_index('ix_retention_executions_started_at', 'retention_executions', ['started_at'])


def downgrade():
    connection = op.get_bind()
    if connection.scalar(sa.text('SELECT count(*) FROM retention_executions')) or connection.scalar(sa.text('SELECT count(*) FROM retention_automation')):
        raise RuntimeError('Preserve automatic retention authorizations and receipts; roll back application images without schema downgrade')
    op.drop_index('ix_retention_executions_started_at', table_name='retention_executions')
    op.drop_table('retention_executions')
    op.drop_table('retention_automation')
    for name in ('retention_eligible_rows','retention_processed_rows','filesystem_available_bytes'):
        op.drop_column('storage_measurements',name)
