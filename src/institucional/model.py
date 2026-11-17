from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Integer, Text, text

from src.database import Base


def _agora() -> datetime:
    return datetime.now(timezone.utc)


class Institucional(Base):
    """
    Conteúdo institucional da página "Quem somos" (US22).

    Registro único: a tabela guarda sempre a linha de id 1. Enquanto ninguém
    salvar, a leitura devolve missão e visão nulas e lista de valores vazia —
    o site não inventa texto.
    """

    __tablename__ = "institucional"

    institucional_id = Column(Integer, primary_key=True)
    missao           = Column(Text, nullable=True)
    visao            = Column(Text, nullable=True)
    valores          = Column(JSON, nullable=False, default=list)
    atualizado_em    = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_agora,
        onupdate=_agora,
        server_default=text("CURRENT_TIMESTAMP"),
    )
