"""add perfil fields to lider

Revision ID: 26e93df0f2ac
Revises: c3a9f1e2d7b4
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "26e93df0f2ac"
down_revision: Union[str, Sequence[str], None] = "c3a9f1e2d7b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("lider", sa.Column("regiao", sa.Text(), nullable=True))
    op.add_column("lider", sa.Column("mini_biografia", sa.Text(), nullable=True))
    op.add_column("lider", sa.Column("redes_sociais", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("lider", "redes_sociais")
    op.drop_column("lider", "mini_biografia")
    op.drop_column("lider", "regiao")
