from sqlalchemy.exc import IntegrityError

from src.banda_palestrante.model import BandaPalestrante
from src.banda_palestrante.repository import RepositorioBandaPalestrante
from src.banda_palestrante.schema import SolicitacaoBandaPalestrante


class ConvidadoVinculadoError(ValueError):
    """US06 (D09): convidado vinculado a evento nao pode ser excluido."""


def _mensagem_vinculado(quantidade: int) -> str:
    eventos = "1 evento" if quantidade == 1 else f"{quantidade} eventos"
    return (
        f"Este convidado está vinculado a {eventos}. "
        "Remova-o da programação antes de excluir."
    )


class ServicoBandaPalestrante:

    def __init__(self, repositorio: RepositorioBandaPalestrante):
        self.repositorio = repositorio

    def criar_banda_palestrante(self, dados: SolicitacaoBandaPalestrante):
        participante = BandaPalestrante(**dados.model_dump())
        return self.repositorio.salvar(participante)

    def listar_banda_palestrantes(self):
        return self.repositorio.buscar_todos()

    def buscar_banda_palestrante(self, participante_id: int):
        participante = self.repositorio.buscar_por_id(participante_id)

        if not participante:
            raise ValueError("Banda ou palestrante não encontrado.")

        return participante

    def atualizar_banda_palestrante(
        self, participante_id: int, dados: SolicitacaoBandaPalestrante
    ):
        participante = self.buscar_banda_palestrante(participante_id)

        for campo, valor in dados.model_dump().items():
            setattr(participante, campo, valor)

        return self.repositorio.atualizar(participante)

    def deletar_banda_palestrante(self, participante_id: int):
        participante = self.buscar_banda_palestrante(participante_id)

        # D09: a exclusao e recusada enquanto houver vinculo com evento. Apagar
        # o vinculo junto mudaria a programacao de um evento sem aviso.
        vinculos = self.repositorio.contar_eventos_vinculados(participante_id)
        if vinculos > 0:
            raise ConvidadoVinculadoError(_mensagem_vinculado(vinculos))

        try:
            self.repositorio.deletar(participante)
        except IntegrityError as erro:
            # Vinculo criado entre a contagem e a exclusao.
            raise ConvidadoVinculadoError(_mensagem_vinculado(1)) from erro
