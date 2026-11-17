from sqlalchemy.orm import Session

from src.formulario.repository import RepositorioFormulario
from src.formulario.schema import (
    RespostaInscricaoFormulario,
    RespostaInscricaoParticipante,
)
from src.pedido.schema import RespostaPedido


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

    def listar_pedidos(
        self,
        db: Session,
        produto_id: int,
    ) -> list[RespostaPedido]:
        """US21: pedidos/interesses registrados no formulario do produto."""
        return self.repositorio.listar_pedidos(db, produto_id)
