"""Persistent provider limits, response observations and bounded rolling accounting."""
from alembic import op
import sqlalchemy as sa

revision = 'rates_20261115'
down_revision = 'bridge_20261115'
branch_labels = None
depends_on = None


def upgrade():
    for column in [
        sa.Column('rate_config', sa.Text()), sa.Column('rate_tokens', sa.Float()),
        sa.Column('rate_token_at', sa.DateTime(timezone=True)),
        sa.Column('rate_inflight_until', sa.DateTime(timezone=True)),
        sa.Column('rate_streak', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('adaptive_until', sa.DateTime(timezone=True)),
        sa.Column('last_rate_limit', sa.DateTime(timezone=True)),
        sa.Column('last_http_success', sa.DateTime(timezone=True)),
        sa.Column('last_recovery', sa.DateTime(timezone=True)),
        sa.Column('rate_observation', sa.Text()),
    ]:
        op.add_column('metadata_providers', column)
    op.alter_column('metadata_providers', 'rate_streak', server_default=None)
    op.create_table('metadata_quota_buckets',
        sa.Column('provider', sa.String(24), sa.ForeignKey('metadata_providers.provider'), primary_key=True),
        sa.Column('resolution', sa.Integer(), primary_key=True),
        sa.Column('started_at', sa.DateTime(timezone=True), primary_key=True),
        sa.Column('used', sa.Integer(), nullable=False))
    # Existing anchored counters, pacing, cooldowns, jobs and secrets are untouched.


def downgrade():
    # Accounting must survive an application rollback. Export and explicitly remove
    # new state before a schema downgrade; ordinary rollback keeps additive schema.
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM metadata_quota_buckets) OR EXISTS (SELECT 1 FROM metadata_providers WHERE rate_config IS NOT NULL OR rate_observation IS NOT NULL OR last_rate_limit IS NOT NULL OR rate_inflight_until IS NOT NULL)")):
        raise RuntimeError('Export provider rate settings and accounting before schema downgrade; roll back application images with additive schema retained')
    op.drop_table('metadata_quota_buckets')
    for name in ['rate_observation', 'last_recovery', 'last_http_success', 'last_rate_limit',
                 'adaptive_until', 'rate_streak', 'rate_inflight_until', 'rate_token_at', 'rate_tokens', 'rate_config']:
        op.drop_column('metadata_providers', name)
