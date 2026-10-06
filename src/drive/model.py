from sqlalchemy import Column, Text, DateTime, func
from src.database import Base


class ImagemCache(Base):
    """
    Cache local das imagens do Google Drive armazenadas em base64.

    Na primeira requisicao de um file_id o backend baixa os bytes do Drive,
    guarda o conteudo aqui e passa a servir as requisicoes seguintes direto do
    banco, sem voltar ao Drive.
    """

    __tablename__ = "imagem_cache"

    file_id         = Column(Text, primary_key=True)
    content_type    = Column(Text, nullable=False)
    conteudo_base64 = Column(Text, nullable=False)
    criado_em       = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
