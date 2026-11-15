"""Versioned metadata catalog providers and recovery queue"""
from alembic import op
import sqlalchemy as sa
revision = 'meta_20261114'
down_revision = '0013'
branch_labels = None
depends_on = None

def upgrade():
    # Additive only: existing observations, prices, accounts and credentials are untouched.
    op.create_table('metadata_providers',
    sa.Column('provider', sa.String(length=24), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('automatic', sa.Boolean(), nullable=False),
    sa.Column('hourly_budget', sa.Integer(), nullable=False),
    sa.Column('daily_budget', sa.Integer(), nullable=False),
    sa.Column('hour_start', sa.DateTime(timezone=True), nullable=True),
    sa.Column('day_start', sa.DateTime(timezone=True), nullable=True),
    sa.Column('hour_used', sa.Integer(), nullable=False),
    sa.Column('day_used', sa.Integer(), nullable=False),
    sa.Column('next_request_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cooldown_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_success', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.String(length=40), nullable=True),
    sa.Column('credential', sa.LargeBinary(), nullable=True),
    sa.Column('credential_key_id', sa.String(length=48), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('credential_status', sa.String(length=32), nullable=False),
    sa.Column('pending_credential', sa.LargeBinary(), nullable=True),
    sa.Column('pending_key_id', sa.String(length=48), nullable=True),
    sa.Column('pending_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('validation_requested', sa.Boolean(), nullable=False),
    sa.Column('validation_revision', sa.Integer(), nullable=False),
    sa.Column('validation_error', sa.String(length=40), nullable=True),
    sa.PrimaryKeyConstraint('provider')
    )
    op.create_table('metadata_sources',
    sa.Column('region', sa.String(length=2), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('locale', sa.String(length=8), nullable=False),
    sa.Column('provider', sa.String(length=24), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('fields_json', sa.Text(), nullable=True),
    sa.Column('source_json', sa.Text(), nullable=True),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('etag', sa.String(length=255), nullable=True),
    sa.Column('checked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('refresh_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('retry_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('http_status', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('region', 'item_id', 'locale', 'provider')
    )
    op.create_index('ix_metadata_sources_due', 'metadata_sources', ['provider', 'retry_at'], unique=False)
    op.create_table('metadata_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('region', sa.String(length=2), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('locale', sa.String(length=8), nullable=False),
    sa.Column('provider', sa.String(length=24), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('fields_json', sa.Text(), nullable=False),
    sa.Column('source_json', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('region', 'item_id', 'locale', 'provider', 'revision', name='uq_metadata_version')
    )
    op.create_table('metadata_jobs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=True),
    sa.Column('market_id', sa.Integer(), nullable=True),
    sa.Column('mode', sa.String(length=16), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('dedupe_key', sa.String(length=64), nullable=False),
    sa.Column('providers_json', sa.Text(), nullable=False),
    sa.Column('total', sa.Integer(), nullable=False),
    sa.Column('request_budget', sa.Integer(), nullable=False),
    sa.Column('requests_used', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['market_id'], ['markets.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_metadata_jobs_dedupe_key'), 'metadata_jobs', ['dedupe_key'], unique=False)
    op.create_index(op.f('ix_metadata_jobs_state'), 'metadata_jobs', ['state'], unique=False)
    op.create_table('metadata_tasks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('job_id', sa.Integer(), nullable=False),
    sa.Column('provider', sa.String(length=24), nullable=False),
    sa.Column('region', sa.String(length=2), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('locale', sa.String(length=8), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('available_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('lease_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('lease_token', sa.String(length=48), nullable=True),
    sa.Column('result_json', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['metadata_jobs.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('job_id', 'provider', 'region', 'item_id', 'locale', name='uq_metadata_job_item')
    )
    op.create_index('ix_metadata_tasks_identity', 'metadata_tasks', ['provider', 'region', 'item_id', 'locale', 'state'], unique=False)
    op.create_index(op.f('ix_metadata_tasks_job_id'), 'metadata_tasks', ['job_id'], unique=False)
    op.create_index('ix_metadata_tasks_queue', 'metadata_tasks', ['state', 'available_at'], unique=False)
    op.add_column('item_metadata', sa.Column('catalog_json', sa.Text(), nullable=True))
    op.add_column('item_metadata', sa.Column('catalog_revision', sa.Integer(), server_default='0', nullable=False))
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('CREATE INDEX ix_item_metadata_catalog_search ON item_metadata USING gin (lower(coalesce(name, fallback_name)) gin_trgm_ops)')
    else:
        op.create_index('ix_item_metadata_catalog_search','item_metadata',[sa.text('lower(coalesce(name, fallback_name))')])


def downgrade():
    connection = op.get_bind()
    if connection.scalar(sa.text('SELECT count(*) FROM metadata_versions')) or connection.scalar(sa.text('SELECT count(*) FROM metadata_jobs')) or connection.scalar(sa.text('SELECT count(*) FROM metadata_providers WHERE credential IS NOT NULL OR pending_credential IS NOT NULL')):
        raise RuntimeError('Export metadata and provider credentials before removing populated metadata tables; application rollback should retain additive schema')
    op.drop_index('ix_item_metadata_catalog_search',table_name='item_metadata')
    op.drop_column('item_metadata', 'catalog_revision')
    op.drop_column('item_metadata', 'catalog_json')
    op.drop_index('ix_metadata_tasks_queue', table_name='metadata_tasks')
    op.drop_index(op.f('ix_metadata_tasks_job_id'), table_name='metadata_tasks')
    op.drop_index('ix_metadata_tasks_identity', table_name='metadata_tasks')
    op.drop_table('metadata_tasks')
    op.drop_index(op.f('ix_metadata_jobs_state'), table_name='metadata_jobs')
    op.drop_index(op.f('ix_metadata_jobs_dedupe_key'), table_name='metadata_jobs')
    op.drop_table('metadata_jobs')
    op.drop_table('metadata_versions')
    op.drop_index('ix_metadata_sources_due', table_name='metadata_sources')
    op.drop_table('metadata_sources')
    op.drop_table('metadata_providers')
    # ### end Alembic commands ###
