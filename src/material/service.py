from src.drive.utils import extrair_file_id_do_google
from src.material.model import Material
from src.material.repository import RepositorioMaterial
from src.material.schema import SolicitacaoMaterial, TipoMaterial


class ServicoMaterial:

    def __init__(self, repositorio: RepositorioMaterial):
        self.repositorio = repositorio

    def criar_material(self, dados: SolicitacaoMaterial) -> Material:
        material = Material(**dados.model_dump(mode="json"))
        return self.repositorio.salvar(material)

    def listar_materiais(self, tipo: TipoMaterial | None = None) -> list[Material]:
        return self.repositorio.buscar_todos(tipo.value if tipo else None)

    def buscar_material(self, material_id: int) -> Material:
        material = self.repositorio.buscar_por_id(material_id)
        if not material:
            raise ValueError("Material não encontrado.")
        return material

    def atualizar_material(self, material_id: int, dados: SolicitacaoMaterial) -> Material:
        material = self.buscar_material(material_id)
        for campo, valor in dados.model_dump(mode="json", exclude_unset=True).items():
            setattr(material, campo, valor)
        return self.repositorio.salvar(material)

    def deletar_material(self, material_id: int) -> None:
        material = self.buscar_material(material_id)
        self.repositorio.deletar(material)

    def arquivo_cadastrado(self, file_id: str) -> bool:
        """Se o arquivo do Drive é um material cadastrado pela superadmin."""
        return any(
            extrair_file_id_do_google(link) == file_id
            for link in self.repositorio.buscar_links()
        )
