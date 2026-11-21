"""Add verified feeds and immutable coverage provenance without rewriting history."""
from alembic import op
import sqlalchemy as sa

revision = 'coverage_20261117'
down_revision = 'recovery_20261117'
branch_labels = depends_on = None


def upgrade():
    op.add_column('markets', sa.Column('unified_coverage', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('observations', sa.Column('source_manifest', sa.Text(), nullable=True))
    op.add_column('snapshot_statistics', sa.Column('source_kind', sa.String(16), nullable=False, server_default='auctions'))
    op.add_column('bridge_derived_records', sa.Column('source_kind', sa.String(16), nullable=False, server_default='auctions'))
    op.add_column('listings', sa.Column('source_kind', sa.String(16), nullable=False, server_default='auctions'))
    op.create_table('feed_captures',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('market_id', sa.Integer(), sa.ForeignKey('markets.id'), nullable=False),
        sa.Column('source_kind', sa.String(16), nullable=False),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('payload_hash', sa.String(64), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('payload_bytes', sa.Integer(), nullable=False),
        sa.Column('compressed_payload', sa.LargeBinary(), nullable=True),
        sa.Column('payload_retained_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('listing_count', sa.Integer(), nullable=False),
        sa.Column('item_count', sa.Integer(), nullable=False),
        sa.UniqueConstraint('market_id', 'source_kind', 'payload_hash'))
    op.create_index('ix_feed_captures_market_id', 'feed_captures', ['market_id'])
    op.create_table('market_feeds',
        sa.Column('market_id', sa.Integer(), sa.ForeignKey('markets.id'), primary_key=True),
        sa.Column('source_kind', sa.String(16), primary_key=True),
        sa.Column('verification', sa.Text(), nullable=False),
        sa.Column('retry_after', sa.DateTime(timezone=True)),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('last_check', sa.DateTime(timezone=True)),
        sa.Column('last_success', sa.DateTime(timezone=True)),
        sa.Column('last_modified', sa.String(100)),
        sa.Column('etag', sa.String(200)),
        sa.Column('failures', sa.Integer(), nullable=False),
        sa.Column('last_error', sa.String(200)),
        sa.Column('capture_id', sa.Integer(), sa.ForeignKey('feed_captures.id')))
    op.create_table('feed_checks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('market_id', sa.Integer(), sa.ForeignKey('markets.id'), nullable=False),
        sa.Column('source_kind', sa.String(16), nullable=False),
        sa.Column('checked_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('http_status', sa.Integer()),
        sa.Column('error', sa.String(200)),
        sa.Column('upstream_modified', sa.String(100)),
        sa.Column('etag', sa.String(200)),
        sa.Column('capture_id', sa.Integer(), sa.ForeignKey('feed_captures.id')))
    op.create_index('ix_feed_checks_market_id', 'feed_checks', ['market_id'])
    op.create_index('ix_feed_checks_checked_at', 'feed_checks', ['checked_at'])
    op.create_table('item_source_coverage',
        sa.Column('market_id', sa.Integer(), sa.ForeignKey('markets.id'), primary_key=True),
        sa.Column('item_id', sa.Integer(), primary_key=True),
        sa.Column('variant_key', sa.String(64), primary_key=True),
        sa.Column('source_kind', sa.String(16), nullable=False),
        sa.Column('first_observed_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    # Images may roll back; never discard genuine feed evidence to roll back code.
    if op.get_bind().scalar(sa.text('SELECT EXISTS(SELECT 1 FROM feed_captures) OR EXISTS(SELECT 1 FROM feed_checks) OR EXISTS(SELECT 1 FROM market_feeds)')):
        raise RuntimeError('Retain feed evidence; use compatible image rollback without schema downgrade')
    op.drop_table('item_source_coverage')
    op.drop_table('feed_checks')
    op.drop_table('market_feeds')
    op.drop_table('feed_captures')
    op.drop_column('listings', 'source_kind')
    op.drop_column('snapshot_statistics', 'source_kind')
    op.drop_column('bridge_derived_records', 'source_kind')
    op.drop_column('observations', 'source_manifest')
    op.drop_column('markets', 'unified_coverage')
