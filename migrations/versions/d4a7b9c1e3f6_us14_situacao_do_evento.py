"""US14: situacao do evento (ativo, cancelado, adiado) e nova data

Revision ID: d4a7b9c1e3f6
Revises: c8f3a6e2d9b4
Create Date: 2026-10-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4a7b9c1e3f6"
down_revision: Union[str, Sequence[str], None] = "c8f3a6e2d9b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Eventos ja cadastrados entram como "ativo".
    op.add_column(
        "evento",
        sa.Column(
            "situacao",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'ativo'"),
        ),
    )
    op.add_column(
        "evento",
        sa.Column("nova_data", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("evento", "nova_data")
    op.drop_column("evento", "situacao")
