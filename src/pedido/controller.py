from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database import obter_banco
from src.pedido.repository import RepositorioPedido
from src.pedido.service import ServicoPedido
from src.pedido.schema import SolicitacaoStatusPedido, RespostaPedido
from src.security import verificar_permissao_setor, SETOR_PRODUTOS

router = APIRouter(prefix="/pedido", tags=["pedido"])


def get_servico(db: Session = Depends(obter_banco)) -> ServicoPedido:
    repositorio = RepositorioPedido(db)
    return ServicoPedido(repositorio)


@router.get("/", response_model=list[RespostaPedido])
def listar_pedidos(
    servico: ServicoPedido = Depends(get_servico),
    _: dict = Depends(verificar_permissao_setor(SETOR_PRODUTOS)),
):
    """
    US21 (CA1): tela de pedidos do setor Comercial. O papel do Keycloak ainda
    se chama "admin-produtos" — a renomeacao para "Comercial" (revisao da
    US03) nao foi implementada em nenhuma ponta, entao a rota reaproveita o
    setor de produtos existente em vez de criar um papel novo.
    """
    return servico.listar_pedidos()


@router.patch("/{pedido_id}/status", response_model=RespostaPedido)
def atualizar_status_pedido(
    pedido_id: int,
    solicitacao: SolicitacaoStatusPedido,
    servico: ServicoPedido = Depends(get_servico),
    _: dict = Depends(verificar_permissao_setor(SETOR_PRODUTOS)),
):
    """US21 (CA2): muda a situacao do pedido, como ja e feito com o voluntario."""
    try:
        return servico.atualizar_status(pedido_id, solicitacao)
    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro
