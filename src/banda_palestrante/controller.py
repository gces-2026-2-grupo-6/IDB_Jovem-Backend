from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import obter_banco
from src.security import verificar_roles, verificar_permissao_setor, SETOR_EVENTOS
from src.banda_palestrante.repository import RepositorioBandaPalestrante
from src.banda_palestrante.service import ServicoBandaPalestrante
from src.banda_palestrante.schema import (
    SolicitacaoBandaPalestrante,
    RespostaBandaPalestrante,
)


router = APIRouter(prefix="/banda-palestrante", tags=["banda-palestrante"])


def get_servico(db: Session = Depends(obter_banco)):
    repositorio = RepositorioBandaPalestrante(db)
    return ServicoBandaPalestrante(repositorio)


@router.post(
    "/",
    response_model=RespostaBandaPalestrante,
    status_code=status.HTTP_201_CREATED,
)
def criar_banda_palestrante(
    solicitacao: SolicitacaoBandaPalestrante,
    servico: ServicoBandaPalestrante = Depends(get_servico),
    _: dict = Depends(verificar_permissao_setor(SETOR_EVENTOS)),
):
    return servico.criar_banda_palestrante(solicitacao)


@router.get("/", response_model=list[RespostaBandaPalestrante])
def listar_banda_palestrantes(
    servico: ServicoBandaPalestrante = Depends(get_servico),
):
    return servico.listar_banda_palestrantes()


@router.get("/{participante_id}", response_model=RespostaBandaPalestrante)
def buscar_banda_palestrante(
    participante_id: int,
    servico: ServicoBandaPalestrante = Depends(get_servico),
):
    try:
        return servico.buscar_banda_palestrante(participante_id)

    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro


@router.put("/{participante_id}", response_model=RespostaBandaPalestrante)
def atualizar_banda_palestrante(
    participante_id: int,
    solicitacao: SolicitacaoBandaPalestrante,
    servico: ServicoBandaPalestrante = Depends(get_servico),
    _: dict = Depends(verificar_permissao_setor(SETOR_EVENTOS)),
):
    try:
        return servico.atualizar_banda_palestrante(participante_id, solicitacao)

    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro


@router.delete("/{participante_id}", status_code=204)
def deletar_banda_palestrante(
    participante_id: int,
    servico: ServicoBandaPalestrante = Depends(get_servico),
    _: dict = Depends(verificar_roles(["superadmin"])),
):
    try:
        servico.deletar_banda_palestrante(participante_id)

    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro
