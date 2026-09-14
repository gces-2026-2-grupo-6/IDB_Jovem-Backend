from sqlalchemy import Column, Integer, Text, Numeric, DateTime, Date, ARRAY
from src.database import Base


class Evento(Base):
    __tablename__ = "evento"

    evento_id            = Column(Integer, primary_key=True, autoincrement=True)
    calendario_evento_id = Column(Text, nullable=True)
    nome                 = Column(Text, nullable=False)
    tipo_evento          = Column(Text, nullable=True)
    descricao            = Column(Text, nullable=True)
    local_latitude       = Column(Numeric(10, 7), nullable=True)
    local_longitude      = Column(Numeric(10, 7), nullable=True)
    data_inicio          = Column(DateTime(timezone=True), nullable=False)
    data_fim             = Column(DateTime(timezone=True), nullable=False)
    link_galeria         = Column(Text, nullable=True)
    nome_local           = Column(Text, nullable=True)
    formulario_link      = Column(Text, nullable=True)
    link_imagem          = Column(Text, nullable=True)
    datas                = Column(ARRAY(Date), nullable=True)
