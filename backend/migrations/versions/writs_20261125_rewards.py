"""Store administrator-maintained base reputation settings independently of catalogue data."""
from alembic import op
import sqlalchemy as sa

revision = 'writs_20261125'
down_revision = 'waylaid_20261125'
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        'crafting_writ_rewards',
        sa.Column('scope', sa.String(4), primary_key=True),
        sa.Column('key', sa.String(48), primary_key=True),
        sa.Column('reputation', sa.Integer()),
        sa.Column('revision', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.CheckConstraint("scope IN ('tier', 'writ')", name='ck_crafting_writ_reward_scope'),
        sa.CheckConstraint('reputation IS NULL OR reputation > 0', name='ck_crafting_writ_reward_positive'),
        sa.CheckConstraint('revision > 0', name='ck_crafting_writ_reward_revision'),
    )


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM crafting_writ_rewards')):
        raise RuntimeError('Preserve Crafting Writ settings by rolling back application images only')
    op.drop_table('crafting_writ_rewards')
