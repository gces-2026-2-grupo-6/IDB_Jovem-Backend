"""merge da inscricao de participante (US09) com o reparo das colunas de lider

Revision ID: e6b2f8a41d07
Revises: 4d7a1c3e8b52, 9c1f3a7d5e24
Create Date: 2026-10-05 18:00:00.000000

A migration da US09 (4d7a1c3e8b52) e o reparo da PR #12 (9c1f3a7d5e24) partem
ambas de 259093bc4c8e. Em vez de reencadear uma depois da outra — o que
deixaria quem ja aplicou a primeira marcado no head sem nunca rodar a segunda,
o mesmo problema que a PR #11 causou —, esta migration une os dois heads:
"alembic upgrade head" aplica o que estiver faltando em qualquer um dos casos.
"""

from typing import Sequence, Union

revision: str = "e6b2f8a41d07"
down_revision: Union[str, Sequence[str], None] = ("4d7a1c3e8b52", "9c1f3a7d5e24")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Nao altera o schema: so une os dois heads."""


def downgrade() -> None:
    """Nao altera o schema: so une os dois heads."""
