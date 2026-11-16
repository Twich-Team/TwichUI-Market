"""Disposable history checkpoint metadata and immutable evidence digests only."""
from alembic import op
import sqlalchemy as sa
revision = 'archive_20261116'
down_revision = 'fdb_20261116'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('archive_digests', sa.Column('snapshot_id', sa.Integer(), primary_key=True),
        sa.Column('algorithm', sa.String(80), primary_key=True), sa.Column('revision', sa.Integer(), primary_key=True),
        sa.Column('record_count', sa.Integer(), nullable=False), sa.Column('records_sha256', sa.String(64), nullable=False),
        sa.Column('records_bytes', sa.BigInteger(), nullable=False))
    op.create_table('archive_checkpoints', sa.Column('checkpoint_id', sa.String(64), primary_key=True),
        sa.Column('market_id', sa.Integer(), sa.ForeignKey('markets.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('credential_id', sa.Integer(), nullable=False), sa.Column('header_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False))
    for field in ('market_id', 'user_id', 'created_at'):
        op.create_index('ix_archive_checkpoints_' + field, 'archive_checkpoints', [field])
    op.create_table('archive_members', sa.Column('checkpoint_id', sa.String(64), sa.ForeignKey('archive_checkpoints.checkpoint_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('phase', sa.Integer(), primary_key=True), sa.Column('source_id', sa.Integer(), primary_key=True),
        sa.Column('value_json', sa.Text(), nullable=False), sa.Column('transmit', sa.Boolean(), nullable=False))


def downgrade():
    op.drop_table('archive_members')
    for field in ('market_id', 'user_id', 'created_at'):
        op.drop_index('ix_archive_checkpoints_' + field, table_name='archive_checkpoints')
    op.drop_table('archive_checkpoints')
    op.drop_table('archive_digests')
