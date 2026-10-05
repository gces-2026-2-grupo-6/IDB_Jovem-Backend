from fastapi import APIRouter, status, HTTPException, Depends
from sqlalchemy.orm import Session

from src.database import obter_banco
from src.evento.repository import RepositorioEvento
from src.atividade.service import ServicoAtividade
from src.atividade.repository import RepositorioAtividade
from src.atividade.schema import RespostaAtividade, SolicitacaoAtividade
from src.security import verificar_permissao_setor, verificar_roles, SETOR_EVENTOS


router = APIRouter(prefix="/evento", tags=["atividade"])


def get_servico(db: Session = Depends(obter_banco)):
    repositorio_atividade = RepositorioAtividade(db)
    repositorio_evento = RepositorioEvento(db)
    return ServicoAtividade(repositorio_atividade, repositorio_evento)


@router.post("/{evento_id}/atividade", response_model=RespostaAtividade, status_code=status.HTTP_201_CREATED)
def criar_atividade(
    evento_id: int,
    solicitar: SolicitacaoAtividade,
    servico: ServicoAtividade = Depends(get_servico),
    _: dict = Depends(verificar_permissao_setor(SETOR_EVENTOS)),
):
    try:
        return servico.criar_atividade(evento_id, solicitar)

    except ValueError as erro:
        raise HTTPException(status_code=400, detail= str(erro)) from erro


@router.get("/{evento_id}/atividade", response_model=list[RespostaAtividade])
def buscar_todas_atividades(evento_id: int, servico: ServicoAtividade = Depends(get_servico)):
    return servico.listar_atividades(evento_id)


@router.get("/atividade/{atividade_id}", response_model=RespostaAtividade)
def buscar_atividade_id(atividade_id: int, servico: ServicoAtividade = Depends(get_servico)):

    try:
        return servico.buscar_atividade(atividade_id)

    except ValueError as erro:
        raise HTTPException(status_code=404, detail= str(erro)) from erro


@router.put("/atividade/{atividade_id}", response_model=RespostaAtividade)
def atualizar_atividade(
    atividade_id: int,
    solicitar: SolicitacaoAtividade,
    servico: ServicoAtividade = Depends(get_servico),
    _: dict = Depends(verificar_permissao_setor(SETOR_EVENTOS)),
):
    try:
        return servico.atualizar_atividade(atividade_id, solicitar)

    except ValueError as erro:
        raise HTTPException(status_code=400, detail = str(erro)) from erro


@router.delete("/atividade/{atividade_id}", status_code=204)
def deletar_atividade(
    atividade_id: int,
    servico: ServicoAtividade = Depends(get_servico),
    _: dict = Depends(verificar_roles(["superadmin"])),
):
    try:
        servico.deletar_atividade(atividade_id)

    except ValueError as erro:
        raise HTTPException(status_code=404, detail = str(erro)) from erro
