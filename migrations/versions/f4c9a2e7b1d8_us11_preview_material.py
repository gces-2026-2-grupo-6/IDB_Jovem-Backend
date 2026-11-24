"""US11: previa visual nos materiais (link_preview opcional)

Revision ID: f4c9a2e7b1d8
Revises: a1b2c3d4e5f7
Create Date: 2026-11-23 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "f4c9a2e7b1d8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("material", sa.Column("link_preview", sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column("material", "link_preview")
