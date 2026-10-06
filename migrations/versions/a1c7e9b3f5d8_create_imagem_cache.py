"""create imagem_cache table

Revision ID: a1c7e9b3f5d8
Revises: c3a9f1e2d7b4
Create Date: 2026-06-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1c7e9b3f5d8"
down_revision: Union[str, Sequence[str], None] = "c3a9f1e2d7b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "imagem_cache",
        sa.Column("file_id", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("conteudo_base64", sa.Text(), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("file_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("imagem_cache")
