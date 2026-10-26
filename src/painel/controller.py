from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import obter_banco
from src.lider.schema import ErroResposta
from src.painel.repository import RepositorioLinkPainel
from src.painel.schema import RespostaLinksPainel, SolicitacaoLinksPainel
from src.painel.service import ServicoLinkPainel
from src.security import verificar_roles

router = APIRouter(prefix="/painel", tags=["painel"])

RESPOSTAS_AUTORIZACAO = {
    401: {"model": ErroResposta, "description": "Token de acesso expirado ou inválido."},
    403: {"model": ErroResposta, "description": "Token ausente ou sem o papel superadmin."},
}


def get_servico(db: Session = Depends(obter_banco)):
    return ServicoLinkPainel(RepositorioLinkPainel(db))


# A planilha reúne dados pessoais de mais de 2500 líderes: os dois links
# ficam restritos à superadministradora, inclusive na leitura.
@router.get(
    "/links",
    response_model=RespostaLinksPainel,
    responses=RESPOSTAS_AUTORIZACAO,
)
def obter_links(
    servico: ServicoLinkPainel = Depends(get_servico),
    _: dict = Depends(verificar_roles(["superadmin"])),
):
    return servico.obter_links()


@router.put(
    "/links",
    response_model=RespostaLinksPainel,
    responses=RESPOSTAS_AUTORIZACAO,
)
def atualizar_links(
    solicitacao: SolicitacaoLinksPainel,
    servico: ServicoLinkPainel = Depends(get_servico),
    _: dict = Depends(verificar_roles(["superadmin"])),
):
    return servico.atualizar_links(solicitacao)
