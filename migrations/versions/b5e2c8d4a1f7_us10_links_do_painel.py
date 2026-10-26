"""US10: links fixados no painel (cadastro e planilha de lideres)

Revision ID: b5e2c8d4a1f7
Revises: 7a3d9e1c5b20
Create Date: 2026-10-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b5e2c8d4a1f7"
down_revision: Union[str, Sequence[str], None] = "7a3d9e1c5b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "link_painel",
        sa.Column("chave", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("chave"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("link_painel")
