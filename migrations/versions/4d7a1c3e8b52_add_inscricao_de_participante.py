"""add inscricao de participante

Revision ID: 4d7a1c3e8b52
Revises: 259093bc4c8e
Create Date: 2026-10-05 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4d7a1c3e8b52'
down_revision: Union[str, None] = '259093bc4c8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Link do formulario de participantes. O `formulario_link` existente
    # continua sendo o do voluntariado (US09: dois fluxos por evento).
    op.add_column(
        'evento',
        sa.Column('formulario_participante_link', sa.Text(), nullable=True),
    )

    op.create_table(
        'participante',
        sa.Column('participante_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('nome', sa.Text(), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('participante_id'),
        sa.UniqueConstraint('email'),
    )

    op.create_table(
        'inscricao',
        sa.Column('participante_id', sa.Integer(), nullable=False),
        sa.Column('evento_id', sa.Integer(), nullable=False),
        sa.Column('resposta_id', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ['participante_id'], ['participante.participante_id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['evento_id'], ['evento.evento_id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('participante_id', 'evento_id'),
    )
    op.create_index('idx_inscricao_evento_id', 'inscricao', ['evento_id'])


def downgrade() -> None:
    op.drop_index('idx_inscricao_evento_id', table_name='inscricao')
    op.drop_table('inscricao')
    op.drop_table('participante')
    op.drop_column('evento', 'formulario_participante_link')
