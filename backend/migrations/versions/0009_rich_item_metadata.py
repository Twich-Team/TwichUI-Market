"""Rich item attributes and independent bounded icon cache."""
from alembic import op
import sqlalchemy as sa
revision='0009'
down_revision='0008'
branch_labels=None
depends_on=None


def upgrade():
    for column in [sa.Column('quality',sa.String(32)),sa.Column('details',sa.Text()),
        sa.Column('resolved_namespace',sa.String(100)),sa.Column('requested_at',sa.DateTime(timezone=True)),
        sa.Column('fallback',sa.Text()),sa.Column('fallback_name',sa.String(255)),sa.Column('fallback_retry_after',sa.DateTime(timezone=True))]:
        op.add_column('item_metadata',column)
    op.create_table('item_media',sa.Column('region',sa.String(2),primary_key=True),sa.Column('item_id',sa.Integer(),primary_key=True),
        sa.Column('status',sa.String(16),nullable=False),sa.Column('source',sa.String(32),nullable=False),
        sa.Column('source_url',sa.String(512)),sa.Column('namespace',sa.String(100)),sa.Column('metadata_hash',sa.String(64)),
        sa.Column('asset_hash',sa.String(64)),sa.Column('content_type',sa.String(32)),sa.Column('data',sa.LargeBinary()),
        sa.Column('byte_count',sa.Integer(),nullable=False),sa.Column('checked_at',sa.DateTime(timezone=True)),
        sa.Column('retry_after',sa.DateTime(timezone=True)),sa.Column('http_status',sa.Integer()),sa.Column('resolved_at',sa.DateTime(timezone=True)))
    # Existing successful name records need one bounded enrichment pass, not a month-long wait.
    op.execute("UPDATE item_metadata SET retry_after=CURRENT_TIMESTAMP WHERE status='available'")


def downgrade():
    op.drop_table('item_media')
    for column in ['fallback_retry_after','fallback_name','fallback','requested_at','resolved_namespace','details','quality']:
        op.drop_column('item_metadata',column)
