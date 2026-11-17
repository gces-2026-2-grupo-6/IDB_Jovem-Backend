"""US22: missao, visao e valores institucionais

Revision ID: d3e5b8a1c4f6
Revises: a7f3c1d9e5b2
Create Date: 2026-11-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d3e5b8a1c4f6"
down_revision: Union[str, Sequence[str], None] = "a7f3c1d9e5b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Registro único: a aplicação usa sempre a linha de id 1. Missão e visão
    # são opcionais porque a página começa sem conteúdo; valores nunca é nulo.
    op.create_table(
        "institucional",
        sa.Column("institucional_id", sa.Integer(), nullable=False),
        sa.Column("missao", sa.Text(), nullable=True),
        sa.Column("visao", sa.Text(), nullable=True),
        sa.Column("valores", sa.JSON(), nullable=False),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("institucional_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("institucional")
