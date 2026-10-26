from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Text, text

from src.database import Base


def _agora() -> datetime:
    return datetime.now(timezone.utc)


class LinkPainel(Base):
    """Link fixado na página inicial do painel (US10), guardado por chave."""

    __tablename__ = "link_painel"

    chave         = Column(Text, primary_key=True)
    url           = Column(Text, nullable=False)
    atualizado_em = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_agora,
        onupdate=_agora,
        server_default=text("CURRENT_TIMESTAMP"),
    )
