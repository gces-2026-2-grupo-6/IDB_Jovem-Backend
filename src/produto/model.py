from sqlalchemy import Column, Integer, Text
from src.database import Base


class Produto(Base):
    __tablename__ = "produto"

    produto_id   = Column(Integer, primary_key=True, autoincrement=True)
    nome         = Column(Text, nullable=False)
    descricao    = Column(Text, nullable=True)
    link_produto = Column(Text, nullable=True)
    link_imagem  = Column(Text, nullable=True)
    # US21: formulario do Google onde o visitante registra o pedido/interesse.
    # A venda e o pagamento continuam externos, pelo link_produto.
    formulario_pedido_link = Column(Text, nullable=True)
