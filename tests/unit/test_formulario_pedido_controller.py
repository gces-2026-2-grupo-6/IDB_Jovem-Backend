"""Controller do fluxo de pedidos (US21)."""
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from src.formulario.controller import listar_pedidos


class TestListarPedidosController:
    def test_sucesso(self):
        mock_servico = MagicMock()
        mock_servico.listar_pedidos.return_value = []
        mock_db = MagicMock()

        resultado = listar_pedidos(produto_id=1, db=mock_db, servico=mock_servico)

        mock_servico.listar_pedidos.assert_called_once_with(mock_db, 1)
        assert resultado == []

    def test_produto_sem_formulario_vira_404(self):
        mock_servico = MagicMock()
        mock_servico.listar_pedidos.side_effect = ValueError(
            "Produto sem formulario de pedidos configurado"
        )

        with pytest.raises(HTTPException) as exc:
            listar_pedidos(produto_id=1, db=MagicMock(), servico=mock_servico)

        assert exc.value.status_code == 404

    def test_produto_nao_encontrado_vira_404(self):
        mock_servico = MagicMock()
        mock_servico.listar_pedidos.side_effect = ValueError("Produto nao encontrado")

        with pytest.raises(HTTPException) as exc:
            listar_pedidos(produto_id=999, db=MagicMock(), servico=mock_servico)

        assert exc.value.status_code == 404

    def test_falha_do_google_vira_502(self):
        mock_servico = MagicMock()
        mock_servico.listar_pedidos.side_effect = RuntimeError("Erro API")

        with pytest.raises(HTTPException) as exc:
            listar_pedidos(produto_id=1, db=MagicMock(), servico=mock_servico)

        assert exc.value.status_code == 502
