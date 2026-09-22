from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database import obter_banco
from src.formulario.repository import RepositorioFormulario
from src.formulario.service import ServicoFormulario
from src.formulario.schema import RespostaInscricaoFormulario
from src.security import verificar_permissao_setor, SETOR_INSCRICOES


router = APIRouter(prefix="/formulario", tags=["Formulario"])

def get_servico():
    """Injeta a dependência do serviço de forma limpa, sem exigir cabeçalhos do front"""
    repositorio = RepositorioFormulario()
    return ServicoFormulario(repositorio)


@router.get(
    "/eventos/{evento_id}/inscricoes",
    response_model=list[RespostaInscricaoFormulario],
)
def listar_inscricoes(
    evento_id: int,
    db: Session = Depends(obter_banco),
    servico: ServicoFormulario = Depends(get_servico),
    _: dict = Depends(verificar_permissao_setor(SETOR_INSCRICOES)),
):
    try:
        return servico.listar_inscricoes(db, evento_id)

    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro

    except RuntimeError as erro:
        raise HTTPException(status_code=502, detail=str(erro)) from erro
