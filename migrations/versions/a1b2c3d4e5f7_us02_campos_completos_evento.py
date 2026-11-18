"""US02: informacoes completas do evento (vagas, contato, valor, pagamento, regulamento)

Revision ID: a1b2c3d4e5f7
Revises: e9c4a2b7f1d3
Create Date: 2026-11-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = "d3e5b8a1c4f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("evento", sa.Column("vagas", sa.Integer(), nullable=True))
    op.add_column(
        "evento", sa.Column("contato_responsavel", sa.Text(), nullable=True)
    )
    op.add_column(
        "evento", sa.Column("valor_investimento", sa.Text(), nullable=True)
    )
    op.add_column("evento", sa.Column("link_pagamento", sa.Text(), nullable=True))
    op.add_column(
        "evento", sa.Column("link_regulamento", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("evento", "link_regulamento")
    op.drop_column("evento", "link_pagamento")
    op.drop_column("evento", "valor_investimento")
    op.drop_column("evento", "contato_responsavel")
    op.drop_column("evento", "vagas")
