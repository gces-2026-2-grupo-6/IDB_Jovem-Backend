from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, Text, text

from src.database import Base


def _agora() -> datetime:
    return datetime.now(timezone.utc)


class Material(Base):
    """
    Material para download (US11). O arquivo continua no Drive: aqui fica só
    o cadastro e o link, sem guardar vídeo ou documento no servidor.
    """

    __tablename__ = "material"

    material_id = Column(Integer, primary_key=True, autoincrement=True)
    titulo      = Column(Text, nullable=False)
    descricao   = Column(Text, nullable=True)
    tipo        = Column(Text, nullable=False)
    link        = Column(Text, nullable=False)
    criado_em   = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_agora,
        server_default=text("CURRENT_TIMESTAMP"),
    )
