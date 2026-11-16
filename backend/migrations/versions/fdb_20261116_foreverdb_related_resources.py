"""Add bounded related-resource caching and durable request identities."""
from alembic import op
import sqlalchemy as sa
revision='fdb_20261116'
down_revision='rates_20261115'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('metadata_tasks',sa.Column('resource',sa.String(80)))
    op.create_table('metadata_resources',
        sa.Column('region',sa.String(2),primary_key=True),
        sa.Column('resource',sa.String(80),primary_key=True),
        sa.Column('offset',sa.Integer(),primary_key=True),
        sa.Column('status',sa.String(32),nullable=False),
        sa.Column('fields_json',sa.Text()),sa.Column('source_json',sa.Text()),
        sa.Column('etag',sa.String(255)),sa.Column('checked_at',sa.DateTime(timezone=True)),
        sa.Column('refresh_at',sa.DateTime(timezone=True)),sa.Column('retry_at',sa.DateTime(timezone=True)),
        sa.Column('http_status',sa.Integer()))


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS(SELECT 1 FROM metadata_resources) OR EXISTS(SELECT 1 FROM metadata_tasks WHERE resource IS NOT NULL)')):
        raise RuntimeError('Retain ForeverDB resource data and queued work during application rollback; export before schema downgrade')
    op.drop_table('metadata_resources')
    op.drop_column('metadata_tasks','resource')
