from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    CheckConstraint,
    func,
    text,
)
from src.database import Base


def _agora() -> datetime:
    return datetime.now(timezone.utc)


class Pedido(Base):
    """
    Pedido/interesse de um visitante por um produto (US21).

    Nasce da sincronizacao com o formulario do Google ligado ao produto
    (`Produto.formulario_pedido_link`) — o mesmo mecanismo ja usado para
    inscricoes de voluntario e de participante (US09). Nao ha rota publica
    de escrita: toda rota de escrita do projeto exige uma guarda de papel
    (test_toda_rota_de_escrita_tem_guarda), e a sincronizacao e quem grava.
    """

    __tablename__ = "pedido"

    pedido_id = Column(Integer, primary_key=True, autoincrement=True)
    produto_id = Column(Integer, ForeignKey("produto.produto_id"), nullable=False)
    nome_solicitante = Column(Text, nullable=False)
    contato_solicitante = Column(Text, nullable=False)
    resposta_id = Column(Text, nullable=True)
    # US21 (CA2): mesmo ciclo do voluntario, com nomes proprios do pedido.
    status = Column(
        Text,
        CheckConstraint(
            "status IN ('pendente', 'em_andamento', 'concluido', 'cancelado')"
        ),
        nullable=False,
        default="pendente",
        server_default=text("'pendente'"),
    )
    # `default` (lado Python) garante o valor no objeto logo apos o flush, sem
    # depender de RETURNING; `server_default` cobre insercao direta via SQL.
    criado_em = Column(
        DateTime(timezone=True),
        default=_agora,
        server_default=func.now(),
        nullable=False,
    )
