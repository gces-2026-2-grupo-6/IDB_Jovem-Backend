from src.institucional.repository import RepositorioInstitucional
from src.institucional.schema import RespostaInstitucional, SolicitacaoInstitucional


class ServicoInstitucional:

    def __init__(self, repositorio: RepositorioInstitucional):
        self.repositorio = repositorio

    def obter_conteudo(self) -> RespostaInstitucional:
        conteudo = self.repositorio.buscar()
        if conteudo is None:
            return RespostaInstitucional(valores=[])
        return RespostaInstitucional.model_validate(conteudo)

    def atualizar_conteudo(
        self, dados: SolicitacaoInstitucional
    ) -> RespostaInstitucional:
        conteudo = self.repositorio.salvar(
            missao=dados.missao,
            visao=dados.visao,
            valores=dados.valores,
        )
        return RespostaInstitucional.model_validate(conteudo)
