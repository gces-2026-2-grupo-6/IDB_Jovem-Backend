from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import obter_banco
from src.security import verificar_roles
from src.lider.repository import RepositorioLider
from src.lider.service import ServicoLider
from src.lider.schema import SolicitacaoLider, RespostaLider, ErroResposta


router = APIRouter(prefix="/lider", tags=["lider"])

# Erros documentados no OpenAPI com o mesmo formato {"detail": "..."}
# devolvido pelo HTTPException. O 422 de validação é declarado pelo FastAPI.
RESPOSTAS_AUTORIZACAO = {
    401: {"model": ErroResposta, "description": "Token de acesso expirado ou inválido."},
    403: {"model": ErroResposta, "description": "Token ausente ou sem o papel superadmin."},
}
RESPOSTA_NAO_ENCONTRADO = {
    404: {"model": ErroResposta, "description": "Líder não encontrado."},
}


def get_servico(db: Session = Depends(obter_banco)):
    repositorio = RepositorioLider(db)
    return ServicoLider(repositorio)


@router.post(
    "/",
    response_model=RespostaLider,
    status_code=status.HTTP_201_CREATED,
    responses=RESPOSTAS_AUTORIZACAO,
)
def criar_lider(
    solicitacao: SolicitacaoLider,
    servico: ServicoLider = Depends(get_servico),
    _: dict = Depends(verificar_roles(["superadmin"])),
):
    return servico.criar_lider(solicitacao)


@router.get("/", response_model=list[RespostaLider])
def listar_lideres(
    servico: ServicoLider = Depends(get_servico),
):
    return servico.listar_lideres()


# As rotas de listagem por situação ficam antes de "/{lider_id}" para não
# serem capturadas pela rota de busca por identificador.
@router.get("/atuais", response_model=list[RespostaLider])
def listar_lideres_atuais(
    servico: ServicoLider = Depends(get_servico),
):
    return servico.listar_lideres_atuais()


@router.get("/diretores-anteriores", response_model=list[RespostaLider])
def listar_diretores_anteriores(
    servico: ServicoLider = Depends(get_servico),
):
    return servico.listar_diretores_anteriores()


@router.get("/{lider_id}", response_model=RespostaLider, responses=RESPOSTA_NAO_ENCONTRADO)
def buscar_lider(
    lider_id: int,
    servico: ServicoLider = Depends(get_servico),
):
    try:
        return servico.buscar_lider(lider_id)

    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro


@router.put(
    "/{lider_id}",
    response_model=RespostaLider,
    responses={**RESPOSTAS_AUTORIZACAO, **RESPOSTA_NAO_ENCONTRADO},
)
def atualizar_lider(
    lider_id: int,
    solicitacao: SolicitacaoLider,
    servico: ServicoLider = Depends(get_servico),
    _: dict = Depends(verificar_roles(["superadmin"])),
):
    try:
        return servico.atualizar_lider(lider_id, solicitacao)

    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro


@router.delete(
    "/{lider_id}",
    status_code=204,
    responses={**RESPOSTAS_AUTORIZACAO, **RESPOSTA_NAO_ENCONTRADO},
)
def deletar_lider(
    lider_id: int,
    servico: ServicoLider = Depends(get_servico),
    _: dict = Depends(verificar_roles(["superadmin"])),
):
    try:
        servico.deletar_lider(lider_id)

    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro
