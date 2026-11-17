from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class StatusPedido(str, Enum):
    PENDENTE = "pendente"
    EM_ANDAMENTO = "em_andamento"
    CONCLUIDO = "concluido"
    CANCELADO = "cancelado"


class SolicitacaoStatusPedido(BaseModel):
    """Corpo do PATCH /pedido/{id}/status (US21 CA2), no mesmo padrao do voluntario."""

    status: StatusPedido


class RespostaPedido(BaseModel):
    """
    US21 (CA1): produto, solicitante e data, no mesmo formato da tela de
    inscricoes. `nome_produto` vem de um join — o pedido guarda so o id.
    """

    pedido_id: int
    produto_id: int
    nome_produto: str
    nome_solicitante: str
    contato_solicitante: str
    status: StatusPedido
    resposta_id: str | None = None
    criado_em: datetime

    class Config:
        from_attributes = True
