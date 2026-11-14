"""Bounded hourly database size measurements."""
from alembic import op
import sqlalchemy as sa
revision='0007'
down_revision='0006'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('storage_measurements',
        sa.Column('sampled_at',sa.DateTime(timezone=True),primary_key=True),
        sa.Column('database_bytes',sa.BigInteger(),nullable=False))


def downgrade():
    op.drop_table('storage_measurements')
