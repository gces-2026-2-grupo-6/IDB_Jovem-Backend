"""add gestao to lider

Revision ID: 7a1d4c9e2b53
Revises: 26e93df0f2ac
Create Date: 2026-10-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7a1d4c9e2b53"
down_revision: Union[str, Sequence[str], None] = "26e93df0f2ac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("lider", sa.Column("gestao", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("lider", "gestao")
