import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException
from src.produto.controller import (
    criar_produto, listar_produtos, buscar_produto,
    atualizar_produto, deletar_produto, get_servico,
)
from src.produto.service import ProdutoComPedidosError


class TestProdutoController:
    def test_get_servico(self):
        mock_db = MagicMock()
        servico = get_servico(db=mock_db)
        from src.produto.service import ServicoProduto
        assert isinstance(servico, ServicoProduto)

    def test_criar_produto_sucesso(self):
        mock_servico = MagicMock()
        mock_servico.criar_produto.return_value = MagicMock()
        resultado = criar_produto(solicitacao=MagicMock(), servico=mock_servico, _={})
        mock_servico.criar_produto.assert_called_once()

    def test_listar_produtos(self):
        mock_servico = MagicMock()
        mock_servico.listar_produtos.return_value = []
        resultado = listar_produtos(servico=mock_servico)
        mock_servico.listar_produtos.assert_called_once()

    def test_buscar_produto_sucesso(self):
        mock_servico = MagicMock()
        mock_servico.buscar_produto.return_value = MagicMock()
        resultado = buscar_produto(produto_id=1, servico=mock_servico)
        mock_servico.buscar_produto.assert_called_once_with(1)

    def test_buscar_produto_nao_encontrado(self):
        mock_servico = MagicMock()
        mock_servico.buscar_produto.side_effect = ValueError("Não encontrado")
        with pytest.raises(HTTPException) as exc:
            buscar_produto(produto_id=1, servico=mock_servico)
        assert exc.value.status_code == 404

    def test_atualizar_produto_sucesso(self):
        mock_servico = MagicMock()
        mock_servico.atualizar_produto.return_value = MagicMock()
        resultado = atualizar_produto(
            produto_id=1, solicitacao=MagicMock(), servico=mock_servico, _={}
        )
        mock_servico.atualizar_produto.assert_called_once()

    def test_atualizar_produto_nao_encontrado(self):
        mock_servico = MagicMock()
        mock_servico.atualizar_produto.side_effect = ValueError("Não encontrado")
        with pytest.raises(HTTPException) as exc:
            atualizar_produto(
                produto_id=1, solicitacao=MagicMock(), servico=mock_servico, _={}
            )
        assert exc.value.status_code == 404

    def test_deletar_produto_sucesso(self):
        mock_servico = MagicMock()
        deletar_produto(produto_id=1, servico=mock_servico, _={})
        mock_servico.deletar_produto.assert_called_once_with(1)

    def test_deletar_produto_nao_encontrado(self):
        mock_servico = MagicMock()
        mock_servico.deletar_produto.side_effect = ValueError("Não encontrado")
        with pytest.raises(HTTPException) as exc:
            deletar_produto(produto_id=1, servico=mock_servico, _={})
        assert exc.value.status_code == 404

    def test_deletar_produto_com_pedidos_vira_409(self):
        """US21: historico de pedidos preservado — exclusao recusada, nao apagada."""
        mock_servico = MagicMock()
        mock_servico.deletar_produto.side_effect = ProdutoComPedidosError(
            "Produto possui pedidos registrados e não pode ser excluído."
        )
        with pytest.raises(HTTPException) as exc:
            deletar_produto(produto_id=1, servico=mock_servico, _={})
        assert exc.value.status_code == 409
