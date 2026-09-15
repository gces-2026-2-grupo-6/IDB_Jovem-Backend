from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import obter_banco
from src.security import verificar_roles
from src.lider.repository import RepositorioLider
from src.lider.service import ServicoLider
from src.lider.schema import SolicitacaoLider, RespostaLider


router = APIRouter(prefix="/lider", tags=["lider"])


def get_servico(db: Session = Depends(obter_banco)):
    repositorio = RepositorioLider(db)
    return ServicoLider(repositorio)


@router.post("/", response_model=RespostaLider, status_code=status.HTTP_201_CREATED)
def criar_lider(
    solicitacao: SolicitacaoLider,
    servico: ServicoLider = Depends(get_servico),
    _: dict = Depends(verificar_roles(["admin", "superadmin"])),
):
    return servico.criar_lider(solicitacao)


@router.get("/", response_model=list[RespostaLider])
def listar_lideres(
    servico: ServicoLider = Depends(get_servico),
):
    return servico.listar_lideres()


@router.get("/{lider_id}", response_model=RespostaLider)
def buscar_lider(
    lider_id: int,
    servico: ServicoLider = Depends(get_servico),
):
    try:
        return servico.buscar_lider(lider_id)

    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro


@router.put("/{lider_id}", response_model=RespostaLider)
def atualizar_lider(
    lider_id: int,
    solicitacao: SolicitacaoLider,
    servico: ServicoLider = Depends(get_servico),
    _: dict = Depends(verificar_roles(["admin", "superadmin"])),
):
    try:
        return servico.atualizar_lider(lider_id, solicitacao)

    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro


@router.delete("/{lider_id}", status_code=204)
def deletar_lider(
    lider_id: int,
    servico: ServicoLider = Depends(get_servico),
    _: dict = Depends(verificar_roles(["superadmin"])),
):
    try:
        servico.deletar_lider(lider_id)

    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro
