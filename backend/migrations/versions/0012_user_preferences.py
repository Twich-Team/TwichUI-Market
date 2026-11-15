"""Versioned, per-user website preferences; independent of market collection.

Revision ID: 0012
Revises: 0011
"""
from alembic import op
import sqlalchemy as sa

revision = '0012'
down_revision = '0011'
branch_labels = depends_on = None


def upgrade():
    op.create_table('user_preferences',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('schema_version', sa.Integer(), nullable=False),
        sa.Column('revision', sa.BigInteger(), nullable=False),
        sa.Column('values_json', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('length(values_json) <= 4096', name='ck_user_preferences_size'))


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM user_preferences')):
        raise RuntimeError('Export user preferences before removing the populated preferences table')
    op.drop_table('user_preferences')
