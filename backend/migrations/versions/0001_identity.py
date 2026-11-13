"""Invitation-only identities, credentials and audit events."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("username", sa.String(64), nullable=False, unique=True),
                    sa.Column("password_hash", sa.Text(), nullable=False),
                    sa.Column("role", sa.String(16), nullable=False),
                    sa.Column("active", sa.Boolean(), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("credentials", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
                    sa.Column("kind", sa.String(16), nullable=False),
                    sa.Column("name", sa.String(80), nullable=False),
                    sa.Column("csrf_hash", sa.String(64)),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("revoked", sa.Boolean(), nullable=False))
    op.create_index("ix_credentials_user_id", "credentials", ["user_id"])
    op.create_table("invitations", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
                    sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("used", sa.Boolean(), nullable=False))
    op.create_table("security_events", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id")),
                    sa.Column("action", sa.String(80), nullable=False),
                    sa.Column("detail", sa.String(200), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("login_attempts", sa.Column("key", sa.String(64), primary_key=True),
                    sa.Column("count", sa.Integer(), nullable=False),
                    sa.Column("window_start", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    for table in ("login_attempts", "security_events", "invitations", "credentials", "users"):
        op.drop_table(table)
