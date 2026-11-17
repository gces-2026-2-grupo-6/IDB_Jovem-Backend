from datetime import datetime, timezone

import pytest
from unittest.mock import MagicMock

from src.pedido.service import ServicoPedido
from src.pedido.model import Pedido
from src.pedido.schema import SolicitacaoStatusPedido


@pytest.fixture
def mock_repositorio():
    return MagicMock()


@pytest.fixture
def servico(mock_repositorio):
    return ServicoPedido(repositorio=mock_repositorio)


def _pedido(pedido_id=1, produto_id=2, status="pendente", resposta_id=None):
    return Pedido(
        pedido_id=pedido_id,
        produto_id=produto_id,
        nome_solicitante="Ana",
        contato_solicitante="ana@exemplo.org",
        status=status,
        resposta_id=resposta_id,
        criado_em=datetime.now(timezone.utc),
    )


def test_listar_pedidos_vazio(servico, mock_repositorio):
    mock_repositorio.buscar_todos_com_produto.return_value = []
    assert servico.listar_pedidos() == []


def test_listar_pedidos_com_varios_traz_produto_e_data(servico, mock_repositorio):
    mock_repositorio.buscar_todos_com_produto.return_value = [
        (_pedido(1, 2), "Camiseta IDB"),
        (_pedido(3, 4), "Boné IDB"),
    ]

    resultado = servico.listar_pedidos()

    assert len(resultado) == 2
    assert resultado[0]["pedido_id"] == 1
    assert resultado[0]["produto_id"] == 2
    assert resultado[0]["nome_produto"] == "Camiseta IDB"
    assert resultado[0]["nome_solicitante"] == "Ana"
    assert resultado[0]["criado_em"] is not None
    assert resultado[1]["nome_produto"] == "Boné IDB"


def test_atualizar_status_sucesso(servico, mock_repositorio):
    pedido = _pedido(status="pendente")
    mock_repositorio.buscar_por_id_com_produto.return_value = (pedido, "Camiseta IDB")
    mock_repositorio.salvar.return_value = pedido

    resultado = servico.atualizar_status(
        1, SolicitacaoStatusPedido(status="em_andamento")
    )

    assert pedido.status == "em_andamento"
    assert resultado["status"] == "em_andamento"
    assert resultado["nome_produto"] == "Camiseta IDB"
    mock_repositorio.salvar.assert_called_once_with(pedido)


@pytest.mark.parametrize(
    "novo_status", ["pendente", "em_andamento", "concluido", "cancelado"]
)
def test_atualizar_status_aceita_todos_os_estados_permitidos(
    servico, mock_repositorio, novo_status
):
    pedido = _pedido(status="pendente")
    mock_repositorio.buscar_por_id_com_produto.return_value = (pedido, "Camiseta IDB")
    mock_repositorio.salvar.return_value = pedido

    resultado = servico.atualizar_status(1, SolicitacaoStatusPedido(status=novo_status))

    assert resultado["status"] == novo_status


def test_atualizar_status_pedido_nao_encontrado(servico, mock_repositorio):
    mock_repositorio.buscar_por_id_com_produto.return_value = None

    with pytest.raises(ValueError, match="Pedido não encontrado."):
        servico.atualizar_status(999, SolicitacaoStatusPedido(status="concluido"))

    mock_repositorio.salvar.assert_not_called()
