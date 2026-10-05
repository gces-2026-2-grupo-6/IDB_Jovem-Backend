from src.lider.model import Lider
from src.lider.repository import RepositorioLider
from src.lider.schema import SolicitacaoLider


class ServicoLider:

    def __init__(self, repositorio: RepositorioLider):
        self.repositorio = repositorio

    def criar_lider(self, dados: SolicitacaoLider):
        lider = Lider(**dados.model_dump())
        return self.repositorio.salvar(lider)

    def listar_lideres(self):
        return self.repositorio.buscar_todos()

    def listar_lideres_atuais(self):
        return self.repositorio.buscar_lideres_atuais()

    def listar_diretores_anteriores(self):
        return self.repositorio.buscar_diretores_anteriores()

    def buscar_lider(self, lider_id: int):
        lider = self.repositorio.buscar_por_id(lider_id)

        if not lider:
            raise ValueError("Líder não encontrado.")

        return lider

    def atualizar_lider(self, lider_id: int, dados: SolicitacaoLider):
        lider = self.buscar_lider(lider_id)

        mudancas = dados.model_dump(exclude_unset=True)

        for campo, valor in mudancas.items():
            setattr(lider, campo, valor)

        return self.repositorio.salvar(lider)

    def deletar_lider(self, lider_id: int):
        lider = self.buscar_lider(lider_id)
        self.repositorio.deletar(lider)
