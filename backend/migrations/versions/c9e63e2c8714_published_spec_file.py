"""Versión documental elegida expresamente para acompañar la convocatoria pública."""
from alembic import op
import sqlalchemy as sa

revision = 'c9e63e2c8714'
down_revision = 'b642a1c0d931'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('publicity_record', sa.Column('portal_version_id', sa.Integer(), nullable=True))
    op.create_index('ix_publicity_record_portal_version_id', 'publicity_record', ['portal_version_id'])
    op.create_foreign_key('fk_publicity_portal_version', 'publicity_record', 'document_version', ['portal_version_id'], ['id'])


def downgrade():
    op.drop_constraint('fk_publicity_portal_version', 'publicity_record', type_='foreignkey')
    op.drop_index('ix_publicity_record_portal_version_id', table_name='publicity_record')
    op.drop_column('publicity_record', 'portal_version_id')
