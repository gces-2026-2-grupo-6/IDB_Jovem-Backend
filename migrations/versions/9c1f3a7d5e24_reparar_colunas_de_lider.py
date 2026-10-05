"""reparar colunas de lider em bancos que pularam as migrations da US05

Revision ID: 9c1f3a7d5e24
Revises: 259093bc4c8e
Create Date: 2026-10-05 00:00:00.000000

A PR #11 reencadeou a migration da US01 (259093bc4c8e) para depois das duas
migrations de lider (26e93df0f2ac e 7a1d4c9e2b53). Quem ja tinha rodado
"alembic upgrade head" antes disso ficou marcado em 259093bc4c8e sem nunca ter
aplicado as duas: o Alembic entende que o banco esta no head e nao reaplica
nada, enquanto a tabela lider fica sem as colunas novas — sem erro nenhum.

Esta migration repara esses bancos sem quebrar os que ja estao corretos: cada
coluna so e criada se ainda nao existir. Depois dela, "alembic upgrade head"
resolve os dois casos.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9c1f3a7d5e24"
down_revision: Union[str, Sequence[str], None] = "259093bc4c8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUNAS = [
    sa.Column("regiao", sa.Text(), nullable=True),
    sa.Column("mini_biografia", sa.Text(), nullable=True),
    sa.Column("redes_sociais", sa.JSON(), nullable=True),
    sa.Column("gestao", sa.Text(), nullable=True),
]


def _existentes() -> set[str]:
    inspetor = sa.inspect(op.get_bind())
    return {coluna["name"] for coluna in inspetor.get_columns("lider")}


def upgrade() -> None:
    existentes = _existentes()
    for coluna in COLUNAS:
        if coluna.name not in existentes:
            op.add_column("lider", coluna)


def downgrade() -> None:
    """Nao remove nada: as colunas pertencem as migrations da US05."""
