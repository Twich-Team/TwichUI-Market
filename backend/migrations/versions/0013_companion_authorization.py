"""Add native device approval/rotation/activity without changing legacy credentials.

Revision ID: 0013
Revises: 0012
"""
from alembic import op
import sqlalchemy as sa

revision = '0013'
down_revision = '0012'
branch_labels = depends_on = None


def upgrade():
    op.create_table('companion_devices',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('name', sa.String(80), nullable=False),
        sa.Column('platform', sa.String(16), nullable=False),
        sa.Column('app_version', sa.String(48), nullable=False),
        sa.Column('issuer_origin', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('refresh_expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False),
        sa.Column('refresh_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('previous_refresh_hash', sa.String(64), unique=True),
        sa.Column('rotation_nonce_hash', sa.String(64)),
        sa.Column('rotated_at', sa.DateTime(timezone=True)),
        sa.Column('generation', sa.Integer(), nullable=False),
        sa.Column('access_credential_id', sa.Integer()),
        sa.Column('last_connection_at', sa.DateTime(timezone=True)),
        sa.Column('last_sync_at', sa.DateTime(timezone=True)),
        sa.Column('selected_market_id', sa.Integer()),
        sa.Column('last_observation_id', sa.Integer()))
    op.create_index('ix_companion_devices_user_id', 'companion_devices', ['user_id'])
    op.add_column('credentials', sa.Column('companion_device_id', sa.Integer(),
        sa.ForeignKey('companion_devices.id', name='fk_credentials_companion_device')))
    op.create_index('ix_credentials_companion_device_id', 'credentials', ['companion_device_id'])
    op.create_table('companion_authorizations',
        sa.Column('id', sa.String(43), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('device_id', sa.Integer(), sa.ForeignKey('companion_devices.id')),
        sa.Column('approved_credential_id', sa.Integer(), sa.ForeignKey('credentials.id')),
        sa.Column('device_name', sa.String(80), nullable=False),
        sa.Column('platform', sa.String(16), nullable=False),
        sa.Column('app_version', sa.String(48), nullable=False),
        sa.Column('issuer_origin', sa.String(255), nullable=False),
        sa.Column('redirect_uri', sa.String(128), nullable=False),
        sa.Column('state_value', sa.String(128), nullable=False),
        sa.Column('state_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('code_challenge', sa.String(43), nullable=False),
        sa.Column('code_hash', sa.String(64), unique=True),
        sa.Column('code_expires_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('invalid_attempts', sa.Integer(), nullable=False))
    op.create_index('ix_companion_authorizations_user_id', 'companion_authorizations', ['user_id'])
    op.create_index('ix_companion_authorizations_expires_at', 'companion_authorizations', ['expires_at'])
    op.create_table('companion_refresh_history',
        sa.Column('token_hash', sa.String(64), primary_key=True),
        sa.Column('device_id', sa.Integer(), sa.ForeignKey('companion_devices.id'), nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_companion_refresh_history_device_id', 'companion_refresh_history', ['device_id'])


def downgrade():
    connection = op.get_bind()
    if connection.scalar(sa.text('SELECT count(*) FROM companion_devices')) or connection.scalar(sa.text('SELECT count(*) FROM companion_authorizations')):
        raise RuntimeError('Export native authorization/device records before removing populated companion tables')
    op.drop_table('companion_refresh_history')
    op.drop_table('companion_authorizations')
    op.drop_index('ix_credentials_companion_device_id', table_name='credentials')
    op.drop_constraint('fk_credentials_companion_device', 'credentials', type_='foreignkey')
    op.drop_column('credentials', 'companion_device_id')
    op.drop_table('companion_devices')
