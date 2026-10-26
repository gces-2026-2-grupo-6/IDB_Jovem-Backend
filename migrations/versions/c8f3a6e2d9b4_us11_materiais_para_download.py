"""US11: materiais para download

Revision ID: c8f3a6e2d9b4
Revises: b5e2c8d4a1f7
Create Date: 2026-10-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8f3a6e2d9b4"
down_revision: Union[str, Sequence[str], None] = "b5e2c8d4a1f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "material",
        sa.Column("material_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("titulo", sa.Text(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("link", sa.Text(), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("material_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("material")
