"""Add bounded immutable bridge exports and independently versioned derivations."""
from alembic import op
import sqlalchemy as sa
revision = 'bridge_20261115'
down_revision = 'meta_20261114'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('bridge_derivations',
        sa.Column('snapshot_id',sa.Integer(),sa.ForeignKey('snapshots.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('algorithm',sa.String(80),primary_key=True),sa.Column('revision',sa.Integer(),primary_key=True),
        sa.Column('record_count',sa.Integer(),nullable=False))
    op.create_table('bridge_derived_records',
        sa.Column('snapshot_id',sa.Integer(),sa.ForeignKey('snapshots.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('algorithm',sa.String(80),primary_key=True),sa.Column('revision',sa.Integer(),primary_key=True),
        sa.Column('item_id',sa.Integer(),primary_key=True),sa.Column('variant_key',sa.String(64),primary_key=True),
        sa.Column('record_json',sa.Text(),nullable=False))
    op.create_table('bridge_generations',sa.Column('generation_id',sa.String(64),primary_key=True),
        sa.Column('market_id',sa.Integer(),sa.ForeignKey('markets.id'),nullable=False),
        sa.Column('algorithm',sa.String(80),nullable=False),sa.Column('source_signature',sa.String(64),nullable=False),
        sa.Column('manifest_json',sa.Text(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_bridge_generations_market_id','bridge_generations',['market_id'])
    op.create_index('ix_bridge_generations_source_signature','bridge_generations',['source_signature'])
    op.create_index('ix_bridge_generations_created_at','bridge_generations',['created_at'])
    op.create_table('bridge_records',sa.Column('generation_id',sa.String(64),sa.ForeignKey('bridge_generations.generation_id',ondelete='CASCADE'),primary_key=True),
        sa.Column('position',sa.Integer(),primary_key=True),sa.Column('record_json',sa.Text(),nullable=False))


def downgrade():
    # Only disposable/rebuildable bridge evidence is removed; original market data is untouched.
    op.drop_table('bridge_records')
    op.drop_index('ix_bridge_generations_created_at',table_name='bridge_generations')
    op.drop_index('ix_bridge_generations_source_signature',table_name='bridge_generations')
    op.drop_index('ix_bridge_generations_market_id',table_name='bridge_generations')
    op.drop_table('bridge_generations')
    op.drop_table('bridge_derived_records')
    op.drop_table('bridge_derivations')
