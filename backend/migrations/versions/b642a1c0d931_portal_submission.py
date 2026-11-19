"""Recepción del formulario digital dentro de un sobre, sin atribuirlo a un funcionario."""
from alembic import op
import sqlalchemy as sa


revision = 'b642a1c0d931'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None

ACTOR_COLUMNS = (('envelope', 'created_by'), ('document', 'created_by'), ('document_version', 'uploaded_by'))


def upgrade():
    for table, column in ACTOR_COLUMNS:
        op.alter_column(table, column, existing_type=sa.Integer(), nullable=True)
    op.create_table('portal_submission',
                    sa.Column('envelope_id', sa.Integer(), sa.ForeignKey('envelope.id'), primary_key=True),
                    sa.Column('retry_key', sa.String(64), nullable=False, unique=True),
                    sa.Column('payload_hash', sa.String(64), nullable=False),
                    sa.Column('original', sa.JSON(), nullable=False))


def downgrade():
    conn = op.get_bind()
    if conn.scalar(sa.text('SELECT COUNT(*) FROM portal_submission')):
        raise RuntimeError('La base contiene ofertas digitales. Conservá sus originales antes de volver a una versión anterior.')
    for table, column in ACTOR_COLUMNS:
        op.alter_column(table, column, existing_type=sa.Integer(), nullable=False)
    op.drop_table('portal_submission')
