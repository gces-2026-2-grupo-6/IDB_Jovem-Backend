from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from src.banda_palestrante.model import BandaPalestrante, Participa


class RepositorioBandaPalestrante:

    def __init__(self, db: Session):
        self.db = db

    def salvar(self, participante: BandaPalestrante) -> BandaPalestrante:
        self.db.add(participante)
        self.db.commit()
        return participante

    def buscar_todos(self) -> list[BandaPalestrante]:
        return self.db.query(BandaPalestrante).all()

    def buscar_por_id(self, participante_id: int) -> BandaPalestrante | None:
        return (
            self.db.query(BandaPalestrante)
            .filter(BandaPalestrante.participante_id == participante_id)
            .first()
        )

    def atualizar(self, participante: BandaPalestrante) -> BandaPalestrante:
        self.db.commit()
        self.db.refresh(participante)
        return participante

    def contar_eventos_vinculados(self, participante_id: int) -> int:
        return (
            self.db.query(Participa)
            .filter(Participa.participante_id == participante_id)
            .count()
        )

    def deletar(self, participante: BandaPalestrante) -> None:
        self.db.delete(participante)
        try:
            self.db.commit()
        except IntegrityError:
            # Devolve a sessao a um estado usavel antes de repassar o erro.
            self.db.rollback()
            raise
