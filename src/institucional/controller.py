from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import obter_banco
from src.institucional.repository import RepositorioInstitucional
from src.institucional.schema import RespostaInstitucional, SolicitacaoInstitucional
from src.institucional.service import ServicoInstitucional
from src.lider.schema import ErroResposta
from src.security import verificar_roles

router = APIRouter(prefix="/institucional", tags=["institucional"])

RESPOSTAS_AUTORIZACAO = {
    401: {"model": ErroResposta, "description": "Token de acesso expirado ou inválido."},
    403: {"model": ErroResposta, "description": "Token ausente ou sem o papel superadmin."},
}


def get_servico(db: Session = Depends(obter_banco)):
    return ServicoInstitucional(RepositorioInstitucional(db))


# Leitura aberta: a página "Quem somos" é pública.
@router.get("", response_model=RespostaInstitucional)
def obter_institucional(servico: ServicoInstitucional = Depends(get_servico)):
    return servico.obter_conteudo()


# Escrita: só a superadministradora edita o conteúdo institucional.
@router.put(
    "",
    response_model=RespostaInstitucional,
    responses=RESPOSTAS_AUTORIZACAO,
)
def atualizar_institucional(
    solicitacao: SolicitacaoInstitucional,
    servico: ServicoInstitucional = Depends(get_servico),
    _: dict = Depends(verificar_roles(["superadmin"])),
):
    return servico.atualizar_conteudo(solicitacao)
