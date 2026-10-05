from sqlalchemy.orm import Session

from src.formulario.repository import RepositorioFormulario
from src.formulario.schema import (
    RespostaInscricaoFormulario,
    RespostaInscricaoParticipante,
)


class ServicoFormulario:

    def __init__(self, repositorio: RepositorioFormulario):
        self.repositorio = repositorio

    def listar_inscricoes(
        self,
        db: Session,
        evento_id: int,
    ) -> list[RespostaInscricaoFormulario]:
        return self.repositorio.listar_inscricoes(db, evento_id)

    def listar_participantes(
        self,
        db: Session,
        evento_id: int,
    ) -> list[RespostaInscricaoParticipante]:
        return self.repositorio.listar_participantes(db, evento_id)
