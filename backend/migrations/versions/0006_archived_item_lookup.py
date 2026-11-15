"""Index retained historical item/variant research."""
from alembic import op
revision='0006'
down_revision='7950caaea602'
branch_labels=None
depends_on=None

def upgrade():
    op.create_index('ix_snapshot_statistics_item_variant','snapshot_statistics',['item_id','variant_key'])

def downgrade():
    op.drop_index('ix_snapshot_statistics_item_variant',table_name='snapshot_statistics')
