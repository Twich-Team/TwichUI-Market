"""Append-only operator live-verification evidence."""
from alembic import op
import sqlalchemy as sa
revision='0008'
down_revision='0007'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('market_verifications',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('market_id',sa.Integer(),sa.ForeignKey('markets.id'),nullable=False),
        sa.Column('actor_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('evidence',sa.Text(),nullable=False),sa.Column('evidence_hash',sa.String(64),nullable=False),
        sa.Column('notes',sa.Text(),nullable=False))
    op.create_index('ix_market_verifications_market_id','market_verifications',['market_id'])


def downgrade():
    op.drop_table('market_verifications')
