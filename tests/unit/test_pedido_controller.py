import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

from src.pedido.controller import listar_pedidos, atualizar_status_pedido, get_servico
from src.pedido.schema import SolicitacaoStatusPedido


class TestPedidoController:
    def test_get_servico(self):
        mock_db = MagicMock()
        servico = get_servico(db=mock_db)
        from src.pedido.service import ServicoPedido
        assert isinstance(servico, ServicoPedido)

    def test_listar_pedidos_vazio(self):
        mock_servico = MagicMock()
        mock_servico.listar_pedidos.return_value = []
        resultado = listar_pedidos(servico=mock_servico, _={})
        mock_servico.listar_pedidos.assert_called_once()
        assert resultado == []

    def test_listar_pedidos_com_varios(self):
        mock_servico = MagicMock()
        mock_servico.listar_pedidos.return_value = [MagicMock(), MagicMock()]
        resultado = listar_pedidos(servico=mock_servico, _={})
        assert len(resultado) == 2

    def test_atualizar_status_sucesso(self):
        mock_servico = MagicMock()
        mock_servico.atualizar_status.return_value = MagicMock()
        resultado = atualizar_status_pedido(
            pedido_id=1,
            solicitacao=SolicitacaoStatusPedido(status="concluido"),
            servico=mock_servico,
            _={},
        )
        mock_servico.atualizar_status.assert_called_once_with(
            1, SolicitacaoStatusPedido(status="concluido")
        )

    def test_atualizar_status_pedido_nao_encontrado(self):
        mock_servico = MagicMock()
        mock_servico.atualizar_status.side_effect = ValueError("Pedido não encontrado.")

        with pytest.raises(HTTPException) as exc:
            atualizar_status_pedido(
                pedido_id=999,
                solicitacao=SolicitacaoStatusPedido(status="concluido"),
                servico=mock_servico,
                _={},
            )
        assert exc.value.status_code == 404
