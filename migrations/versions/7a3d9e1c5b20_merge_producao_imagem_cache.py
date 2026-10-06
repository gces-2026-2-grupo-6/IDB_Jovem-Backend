"""merge da main do grupo com a tabela imagem_cache que ja esta em producao

Revision ID: 7a3d9e1c5b20
Revises: e6b2f8a41d07, a1c7e9b3f5d8
Create Date: 2026-10-06 19:30:00.000000

O banco de producao (VPS) esta em a1c7e9b3f5d8, migration que so existia no
repositorio IDBJovem e nunca chegou a main do grupo. As duas linhas partem de
c3a9f1e2d7b4. Esta migration une os dois heads: "alembic upgrade head" aplica
em producao tudo o que o grupo fez, e num banco novo cria tambem imagem_cache.
"""

from typing import Sequence, Union

revision: str = "7a3d9e1c5b20"
down_revision: Union[str, Sequence[str], None] = ("e6b2f8a41d07", "a1c7e9b3f5d8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Nao altera o schema: so une os dois heads."""


def downgrade() -> None:
    """Nao altera o schema: so une os dois heads."""
