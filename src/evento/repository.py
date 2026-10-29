from sqlalchemy.orm import Session
from sqlalchemy import text
from src.evento.model import Evento, FotoExcluidaEvento
from src.banda_palestrante.model import BandaPalestrante, Participa


class RepositorioEvento:

    def __init__(self, db: Session):
        self.db = db

    def salvar(self, evento: Evento) -> Evento:
        if evento.evento_id:
            self.db.merge(evento)
        else:
            self.db.add(evento)
        self.db.commit()
        return evento

    def buscar_todos(self) -> list[Evento]:
        return self.db.query(Evento).all()

    def buscar_por_id(self, evento_id: int) -> Evento:
        return self.db.query(Evento).filter(Evento.evento_id == evento_id).first()

    def deletar(self, evento) -> None:
        if evento is not None:
            self.db.delete(evento)
            self.db.commit()

    def pesquisar_por_nome(self, termo: str) -> list[Evento]:
        sql = text("""
            SELECT *
            FROM evento
            WHERE similarity(nome, :termo) > 0.2
            OR nome ILIKE :termo_like
            ORDER BY similarity(nome, :termo) DESC
        """)

        return self.db.query(Evento).from_statement(sql).params(
            termo=termo,
            termo_like=f"%{termo}%"
        ).all()

    def buscar_participantes(self, evento_id: int) -> list[BandaPalestrante]:
        return (
            self.db.query(BandaPalestrante)
            .join(
                Participa,
                Participa.participante_id == BandaPalestrante.participante_id,
            )
            .filter(Participa.evento_id == evento_id)
            .all()
        )

    def buscar_participante_por_id(self, participante_id: int) -> BandaPalestrante | None:
        return (
            self.db.query(BandaPalestrante)
            .filter(BandaPalestrante.participante_id == participante_id)
            .first()
        )

    def buscar_vinculo(self, evento_id: int, participante_id: int) -> Participa | None:
        return (
            self.db.query(Participa)
            .filter(
                Participa.evento_id == evento_id,
                Participa.participante_id == participante_id,
            )
            .first()
        )

    def vincular_participante(self, evento_id: int, participante_id: int) -> Participa:
        vinculo = Participa(evento_id=evento_id, participante_id=participante_id)
        self.db.add(vinculo)
        self.db.commit()
        return vinculo

    def desvincular_participante(self, vinculo: Participa) -> None:
        self.db.delete(vinculo)
        self.db.commit()

    def buscar_fotos_excluidas(self, evento_id: int) -> set[str]:
        registros = (
            self.db.query(FotoExcluidaEvento)
            .filter(FotoExcluidaEvento.evento_id == evento_id)
            .all()
        )
        return {registro.foto_id for registro in registros}

    def registrar_fotos_excluidas(self, evento_id: int, foto_ids: list[str]) -> None:
        ja_excluidas = self.buscar_fotos_excluidas(evento_id)
        novas = [
            FotoExcluidaEvento(evento_id=evento_id, foto_id=foto_id)
            for foto_id in foto_ids
            if foto_id not in ja_excluidas
        ]
        if novas:
            self.db.add_all(novas)
            self.db.commit()
