"""Reversible member/device display archives; retain security ownership."""
from alembic import op
import sqlalchemy as sa
revision = 'usability_20261117'
down_revision = 'archive_20261116'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('archived_at', sa.DateTime(timezone=True)))
    op.add_column('companion_devices', sa.Column('archived_at', sa.DateTime(timezone=True)))


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS(SELECT 1 FROM users WHERE archived_at IS NOT NULL) OR EXISTS(SELECT 1 FROM companion_devices WHERE archived_at IS NOT NULL)')):
        raise RuntimeError('Restore archived entries before dropping display archive state')
    op.drop_column('companion_devices', 'archived_at')
    op.drop_column('users', 'archived_at')
