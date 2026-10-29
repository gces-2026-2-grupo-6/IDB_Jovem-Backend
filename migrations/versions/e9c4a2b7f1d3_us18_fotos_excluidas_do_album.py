"""US18: fotos excluidas do album de um evento no site

Revision ID: e9c4a2b7f1d3
Revises: f1e2d3c4b5a6
Create Date: 2026-10-28 19:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e9c4a2b7f1d3"
down_revision: Union[str, Sequence[str], None] = "f1e2d3c4b5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "evento_foto_excluida",
        sa.Column("evento_id", sa.Integer(), nullable=False),
        sa.Column("foto_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["evento_id"],
            ["evento.evento_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("evento_id", "foto_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("evento_foto_excluida")

