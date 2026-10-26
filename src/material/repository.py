from sqlalchemy.orm import Session

from src.material.model import Material


class RepositorioMaterial:

    def __init__(self, db: Session):
        self.db = db

    def salvar(self, material: Material) -> Material:
        self.db.add(material)
        self.db.commit()
        self.db.refresh(material)
        return material

    def buscar_todos(self, tipo: str | None = None) -> list[Material]:
        consulta = self.db.query(Material)
        if tipo:
            consulta = consulta.filter(Material.tipo == tipo)
        return consulta.order_by(Material.criado_em.desc(), Material.material_id.desc()).all()

    def buscar_por_id(self, material_id: int) -> Material | None:
        return self.db.query(Material).filter(Material.material_id == material_id).first()

    def buscar_links(self) -> list[str]:
        return [link for (link,) in self.db.query(Material.link).all()]

    def deletar(self, material: Material) -> None:
        self.db.delete(material)
        self.db.commit()
