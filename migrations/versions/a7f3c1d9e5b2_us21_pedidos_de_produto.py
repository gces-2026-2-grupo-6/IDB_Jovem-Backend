"""US21: pedidos/interesses de produto registrados pelo setor Comercial

Revision ID: a7f3c1d9e5b2
Revises: e9c4a2b7f1d3
Create Date: 2026-11-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7f3c1d9e5b2"
down_revision: Union[str, Sequence[str], None] = "e9c4a2b7f1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Produto existente fica sem formulario de pedidos ate alguem configurar
    # um (CA1/CA2 so afetam a tela de pedidos, nao o cadastro ja existente).
    op.add_column(
        "produto",
        sa.Column("formulario_pedido_link", sa.Text(), nullable=True),
    )

    op.create_table(
        "pedido",
        sa.Column("pedido_id", sa.Integer(), nullable=False),
        sa.Column("produto_id", sa.Integer(), nullable=False),
        sa.Column("nome_solicitante", sa.Text(), nullable=False),
        sa.Column("contato_solicitante", sa.Text(), nullable=False),
        sa.Column("resposta_id", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pendente'"),
        ),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('pendente', 'em_andamento', 'concluido', 'cancelado')",
            name="ck_pedido_status",
        ),
        sa.ForeignKeyConstraint(["produto_id"], ["produto.produto_id"]),
        sa.PrimaryKeyConstraint("pedido_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("pedido")
    op.drop_column("produto", "formulario_pedido_link")
