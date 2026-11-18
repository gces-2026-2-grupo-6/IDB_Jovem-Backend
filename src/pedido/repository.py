from sqlalchemy.orm import Session

from src.pedido.model import Pedido
from src.produto.model import Produto


class RepositorioPedido:

    def __init__(self, db: Session):
        self.db = db

    def salvar(self, pedido: Pedido) -> Pedido:
        self.db.add(pedido)
        self.db.commit()
        return pedido

    def buscar_por_id(self, pedido_id: int) -> Pedido | None:
        return self.db.query(Pedido).filter(Pedido.pedido_id == pedido_id).first()

    def buscar_todos_com_produto(self) -> list[tuple[Pedido, str]]:
        """Lista geral da tela de pedidos (US21 CA1), mais recente primeiro."""
        return (
            self.db.query(Pedido, Produto.nome)
            .join(Produto, Produto.produto_id == Pedido.produto_id)
            .order_by(Pedido.criado_em.desc())
            .all()
        )

    def buscar_por_id_com_produto(self, pedido_id: int) -> tuple[Pedido, str] | None:
        return (
            self.db.query(Pedido, Produto.nome)
            .join(Produto, Produto.produto_id == Pedido.produto_id)
            .filter(Pedido.pedido_id == pedido_id)
            .first()
        )

    def contar_por_produto(self, produto_id: int) -> int:
        """US21: usado pelo produto para recusar exclusao com historico vinculado."""
        return self.db.query(Pedido).filter(Pedido.produto_id == produto_id).count()
