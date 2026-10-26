import unicodedata

from src.lider.model import Lider
from src.lider.repository import RepositorioLider
from src.lider.schema import SolicitacaoLider


class CargoOcupadoError(ValueError):
    """Já existe um líder ativo no mesmo cargo e na mesma abrangência (RF58)."""


def _normalizar(texto: str | None) -> str:
    """
    Deixa o texto comparável: sem acento, sem diferença de caixa, com hífen
    tratado como espaço e espaços repetidos colapsados. Assim "Vice-Diretor
    Nacional" e "vice diretor nacional" contam como o mesmo cargo.
    """
    if not texto:
        return ""
    sem_acento = "".join(
        letra
        for letra in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(letra)
    )
    return " ".join(sem_acento.casefold().replace("-", " ").split())


class ServicoLider:

    def __init__(self, repositorio: RepositorioLider):
        self.repositorio = repositorio

    def _garantir_cargo_livre(
        self,
        cargo: str,
        regiao: str | None,
        is_antigo: bool,
        ignorar_id: int | None = None,
    ) -> None:
        """
        US10 / RF58: dois líderes ativos não podem ocupar o mesmo cargo.

        O cargo é o par (cargo, região). "Diretor Regional" do Sul e do Centro
        Oeste são cargos diferentes e convivem. Diretor anterior (is_antigo)
        não ocupa cargo, então marcar o antecessor como anterior libera a vaga.
        """
        if is_antigo:
            return

        chave = (_normalizar(cargo), _normalizar(regiao))
        for lider in self.repositorio.buscar_lideres_atuais():
            if lider.lider_id == ignorar_id:
                continue
            if (_normalizar(lider.cargo), _normalizar(lider.regiao)) == chave:
                abrangencia = f" na região {lider.regiao}" if lider.regiao else ""
                raise CargoOcupadoError(
                    f"O cargo '{cargo}'{abrangencia} já está ocupado por "
                    f"{lider.nome}. Marque o líder atual como diretor anterior "
                    "antes de cadastrar o novo."
                )

    def criar_lider(self, dados: SolicitacaoLider):
        self._garantir_cargo_livre(dados.cargo, dados.regiao, dados.is_antigo)
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

        # A regra vale também na edição: sem isso o cargo duplicado volta por PUT.
        self._garantir_cargo_livre(
            mudancas.get("cargo", lider.cargo),
            mudancas.get("regiao", lider.regiao),
            mudancas.get("is_antigo", lider.is_antigo),
            ignorar_id=lider.lider_id,
        )

        for campo, valor in mudancas.items():
            setattr(lider, campo, valor)

        return self.repositorio.salvar(lider)

    def deletar_lider(self, lider_id: int):
        lider = self.buscar_lider(lider_id)
        self.repositorio.deletar(lider)
