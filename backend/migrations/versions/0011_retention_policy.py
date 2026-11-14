"""Administrator retention proposals and bounded compaction receipts.

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa
revision = '0011'
down_revision = '0010'
branch_labels = depends_on = None

def upgrade():
    op.create_table('player_market_mappings',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('region',sa.String(2),nullable=False),sa.Column('ruleset',sa.String(32),nullable=False),
        sa.Column('faction',sa.String(16),nullable=False),sa.Column('house_id',sa.Integer(),nullable=False),
        sa.Column('transport_ruleset_id',sa.Integer(),nullable=False),sa.Column('source_kind',sa.String(16),nullable=False),
        sa.Column('confidence',sa.String(32),nullable=False),sa.Column('evidence',sa.Text(),nullable=False),
        sa.Column('evidence_hash',sa.String(64),nullable=False),sa.Column('verified_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('region','ruleset','faction','source_kind'),sa.UniqueConstraint('region','house_id','source_kind'))
    op.create_table('retention_policy', sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('revision',sa.Integer(),nullable=False),
        *[sa.Column(name,sa.Integer(),nullable=False) for name in ['raw_days','intraday_days','daily_days','operational_days','security_days']],
        sa.Column('approved_hash',sa.String(64)),sa.Column('approved_at',sa.DateTime(timezone=True)),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.create_table('retention_batches',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('actor_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('policy_hash',sa.String(64),nullable=False),sa.Column('stage',sa.String(32),nullable=False),
        sa.Column('rows_removed',sa.Integer(),nullable=False),sa.Column('cutoff',sa.DateTime(timezone=True),nullable=False),
        sa.Column('history_floor',sa.DateTime(timezone=True)),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_table('retention_policy_changes',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('actor_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('before',sa.Text(),nullable=False),sa.Column('after',sa.Text(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_retention_batches_created_at','retention_batches',['created_at'])
    op.create_index('ix_collection_runs_checked_at','collection_runs',['checked_at'])
    op.create_index('ix_security_events_created_at','security_events',['created_at'])

def downgrade():
    connection=op.get_bind()
    if any(connection.scalar(sa.text(f'SELECT count(*) FROM {table}')) for table in ('retention_batches','retention_policy','retention_policy_changes','player_market_mappings')):
        raise RuntimeError('Export retention policy/receipts and use documented recovery before downgrade')
    op.drop_index('ix_security_events_created_at',table_name='security_events')
    op.drop_index('ix_collection_runs_checked_at',table_name='collection_runs')
    op.drop_index('ix_retention_batches_created_at',table_name='retention_batches')
    op.drop_table('retention_policy_changes')
    op.drop_table('retention_batches')
    op.drop_table('retention_policy')
    op.drop_table('player_market_mappings')
