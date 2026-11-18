from src.pedido.model import Pedido
from src.pedido.repository import RepositorioPedido
from src.pedido.schema import SolicitacaoStatusPedido


def _para_resposta(pedido: Pedido, nome_produto: str) -> dict:
    return {
        "pedido_id": pedido.pedido_id,
        "produto_id": pedido.produto_id,
        "nome_produto": nome_produto,
        "nome_solicitante": pedido.nome_solicitante,
        "contato_solicitante": pedido.contato_solicitante,
        "status": pedido.status,
        "resposta_id": pedido.resposta_id,
        "criado_em": pedido.criado_em,
    }


class ServicoPedido:

    def __init__(self, repositorio: RepositorioPedido):
        self.repositorio = repositorio

    def listar_pedidos(self) -> list[dict]:
        """US21 (CA1): pedidos recebidos, com produto, solicitante e data."""
        return [
            _para_resposta(pedido, nome_produto)
            for pedido, nome_produto in self.repositorio.buscar_todos_com_produto()
        ]

    def atualizar_status(self, pedido_id: int, dados: SolicitacaoStatusPedido) -> dict:
        """US21 (CA2): muda a situacao do pedido, como ja e feito com o voluntario."""
        resultado = self.repositorio.buscar_por_id_com_produto(pedido_id)

        if not resultado:
            raise ValueError("Pedido não encontrado.")

        pedido, nome_produto = resultado
        pedido.status = dados.status.value
        pedido = self.repositorio.salvar(pedido)
        return _para_resposta(pedido, nome_produto)
