from src.painel.repository import RepositorioLinkPainel
from src.painel.schema import RespostaLinksPainel, SolicitacaoLinksPainel


class ServicoLinkPainel:

    def __init__(self, repositorio: RepositorioLinkPainel):
        self.repositorio = repositorio

    def obter_links(self) -> RespostaLinksPainel:
        salvos = self.repositorio.buscar_todos()
        return RespostaLinksPainel(
            **{
                campo: salvos.get(campo)
                for campo in RespostaLinksPainel.model_fields
            }
        )

    def atualizar_links(self, dados: SolicitacaoLinksPainel) -> RespostaLinksPainel:
        for chave, url in dados.model_dump(exclude_unset=True).items():
            self.repositorio.salvar(chave, url)
        return self.obter_links()
