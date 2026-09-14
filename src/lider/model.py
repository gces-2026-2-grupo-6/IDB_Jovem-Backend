from sqlalchemy import Column, Integer, Text, Boolean, JSON
from src.database import Base

class Lider(Base):
    __tablename__ = "lider"

    lider_id       = Column(Integer, primary_key=True, autoincrement=True)
    nome           = Column(Text, nullable=False)
    cargo          = Column(Text, nullable=False)
    imagem_url     = Column(Text, nullable=True)
    is_antigo      = Column(Boolean, nullable=False, default=False)
    ordem          = Column(Integer, nullable=False, default=0)
    regiao         = Column(Text, nullable=True)
    mini_biografia = Column(Text, nullable=True)
    redes_sociais  = Column(JSON, nullable=True)
