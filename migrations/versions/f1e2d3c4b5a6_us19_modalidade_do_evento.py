"""US19: modalidade do evento (presencial, online) e link de transmissao

Revision ID: f1e2d3c4b5a6
Revises: d4a7b9c1e3f6
Create Date: 2026-10-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1e2d3c4b5a6"
down_revision: Union[str, Sequence[str], None] = "d4a7b9c1e3f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Eventos ja cadastrados sao tratados como "presencial" (CA4).
    op.add_column(
        "evento",
        sa.Column(
            "modalidade",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'presencial'"),
        ),
    )
    op.add_column(
        "evento",
        sa.Column("link_transmissao", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("evento", "link_transmissao")
    op.drop_column("evento", "modalidade")
