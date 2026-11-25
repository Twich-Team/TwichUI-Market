"""Add durable administrator-maintained Waylaid Crates rewards."""
from alembic import op
import sqlalchemy as sa

revision = 'waylaid_20261125'
down_revision = 'retention_20261118'
branch_labels = depends_on = None

DEFAULTS = {'apprentice': 5, 'journeyman': 10, 'expert': 15, 'artisan': None}


def upgrade():
    table = op.create_table(
        'waylaid_rewards',
        sa.Column('tier', sa.String(48), primary_key=True),
        sa.Column('favor', sa.Integer()),
        sa.Column('revision', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.CheckConstraint('favor IS NULL OR favor > 0', name='ck_waylaid_rewards_favor_positive'),
        sa.CheckConstraint('revision > 0', name='ck_waylaid_rewards_revision_positive'),
    )
    op.bulk_insert(table, [
        {'tier': tier, 'favor': favor, 'revision': 1, 'updated_at': None, 'updated_by': None}
        for tier, favor in DEFAULTS.items()
    ])


def downgrade():
    edited = op.get_bind().scalar(sa.text(
        'SELECT count(*) FROM waylaid_rewards WHERE updated_at IS NOT NULL OR revision <> 1'
    ))
    if edited:
        raise RuntimeError('Preserve Waylaid Crates settings by rolling back application images only')
    op.drop_table('waylaid_rewards')
