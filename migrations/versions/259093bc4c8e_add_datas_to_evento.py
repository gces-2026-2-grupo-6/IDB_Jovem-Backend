"""add datas to evento

Revision ID: 259093bc4c8e
Revises: 7a1d4c9e2b53
Create Date: 2026-09-14 19:32:42.544521

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '259093bc4c8e'
down_revision: Union[str, None] = '7a1d4c9e2b53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('evento', sa.Column('datas', sa.ARRAY(sa.Date()), nullable=True))


def downgrade() -> None:
    op.drop_column('evento', 'datas')
