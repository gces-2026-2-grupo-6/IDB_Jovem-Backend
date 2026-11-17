from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import obter_banco
from src.security import verificar_roles, verificar_permissao_setor, SETOR_PRODUTOS
from src.produto.repository import RepositorioProduto
from src.produto.service import ServicoProduto, ProdutoComPedidosError
from src.produto.schema import SolicitacaoProduto, RespostaProduto
from src.pedido.repository import RepositorioPedido


router = APIRouter(prefix="/produto", tags=["produto"])


def get_servico(db: Session = Depends(obter_banco)):
    repositorio = RepositorioProduto(db)
    repositorio_pedido = RepositorioPedido(db)
    return ServicoProduto(repositorio, repositorio_pedido)


@router.post("/", response_model=RespostaProduto, status_code=status.HTTP_201_CREATED)
def criar_produto(
    solicitacao: SolicitacaoProduto,
    servico: ServicoProduto = Depends(get_servico),
    _: dict = Depends(verificar_permissao_setor(SETOR_PRODUTOS)),
):
    return servico.criar_produto(solicitacao)


@router.get("/", response_model=list[RespostaProduto])
def listar_produtos(
    servico: ServicoProduto = Depends(get_servico),
):
    return servico.listar_produtos()


@router.get("/{produto_id}", response_model=RespostaProduto)
def buscar_produto(
    produto_id: int,
    servico: ServicoProduto = Depends(get_servico),
):
    try:
        return servico.buscar_produto(produto_id)

    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro


@router.put("/{produto_id}", response_model=RespostaProduto)
def atualizar_produto(
    produto_id: int,
    solicitacao: SolicitacaoProduto,
    servico: ServicoProduto = Depends(get_servico),
    _: dict = Depends(verificar_permissao_setor(SETOR_PRODUTOS)),
):
    try:
        return servico.atualizar_produto(produto_id, solicitacao)

    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro


@router.delete("/{produto_id}", status_code=204)
def deletar_produto(
    produto_id: int,
    servico: ServicoProduto = Depends(get_servico),
    _: dict = Depends(verificar_roles(["superadmin"])),
):
    try:
        servico.deletar_produto(produto_id)

    except ProdutoComPedidosError as erro:
        raise HTTPException(status_code=409, detail=str(erro)) from erro

    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro
