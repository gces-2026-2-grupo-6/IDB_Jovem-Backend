from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import obter_banco
from src.security import verificar_roles, verificar_permissao_setor, SETOR_INSCRICOES
from src.voluntario.repository import RepositorioVoluntario
from src.voluntario.service import ServicoVoluntario
from src.voluntario.schema import (
    SolicitacaoVoluntario,
    RespostaVoluntario,
    RespostaTrabalhoVoluntario,
)


router = APIRouter(prefix="/voluntarios", tags=["voluntarios"])


def get_servico(db: Session = Depends(obter_banco)):
    repositorio = RepositorioVoluntario(db)
    return ServicoVoluntario(repositorio)


@router.post("/", response_model=RespostaVoluntario, status_code=status.HTTP_201_CREATED)
def criar_voluntario(
    solicitacao: SolicitacaoVoluntario,
    servico: ServicoVoluntario = Depends(get_servico),
    _: dict = Depends(verificar_permissao_setor(SETOR_INSCRICOES)),
):
    try:
        return servico.criar_voluntario(solicitacao)

    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro


@router.get("/", response_model=list[RespostaVoluntario])
def listar_voluntarios(
    servico: ServicoVoluntario = Depends(get_servico),
    _: dict = Depends(verificar_permissao_setor(SETOR_INSCRICOES)),
):
    return servico.listar_voluntarios()


@router.get("/{voluntario_id}", response_model=RespostaVoluntario)
def buscar_voluntario(
    voluntario_id: int,
    servico: ServicoVoluntario = Depends(get_servico),
    _: dict = Depends(verificar_permissao_setor(SETOR_INSCRICOES)),
):
    try:
        return servico.buscar_voluntario(voluntario_id)

    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro


@router.delete("/{voluntario_id}", status_code=204)
def deletar_voluntario(
    voluntario_id: int,
    servico: ServicoVoluntario = Depends(get_servico),
    _: dict = Depends(verificar_roles(["superadmin"])),
):
    try:
        servico.deletar_voluntario(voluntario_id)

    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro


@router.get("/evento/{evento_id}", response_model=list[RespostaTrabalhoVoluntario])
def listar_voluntarios_evento(
    evento_id: int,
    servico: ServicoVoluntario = Depends(get_servico),
    _: dict = Depends(verificar_permissao_setor(SETOR_INSCRICOES)),
):
    return servico.listar_voluntarios_evento(evento_id)


@router.patch("/{voluntario_id}/evento/{evento_id}/status", response_model=RespostaTrabalhoVoluntario)
def atualizar_status_voluntario(
    voluntario_id: int,
    evento_id: int,
    novo_status: str,
    servico: ServicoVoluntario = Depends(get_servico),
    _: dict = Depends(verificar_permissao_setor(SETOR_INSCRICOES)),
):
    try:
        return servico.atualizar_status(voluntario_id, evento_id, novo_status)

    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro


@router.get("/evento/{evento_id}/contagem")
def contar_voluntarios_evento(
    evento_id: int,
    servico: ServicoVoluntario = Depends(get_servico),
    _: dict = Depends(verificar_permissao_setor(SETOR_INSCRICOES)),
):
    return servico.contar_voluntarios_evento(evento_id)
