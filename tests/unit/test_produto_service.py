import pytest
from unittest.mock import MagicMock
from src.produto.service import ServicoProduto, ProdutoComPedidosError
from src.produto.model import Produto
from src.produto.schema import SolicitacaoProduto


@pytest.fixture
def mock_repositorio():
    return MagicMock()


@pytest.fixture
def mock_repositorio_pedido():
    """US21: por padrao, sem pedidos vinculados — produto pode ser excluido."""
    mock = MagicMock()
    mock.contar_por_produto.return_value = 0
    return mock


@pytest.fixture
def servico(mock_repositorio, mock_repositorio_pedido):
    return ServicoProduto(
        repositorio=mock_repositorio, repositorio_pedido=mock_repositorio_pedido
    )


def test_criar_produto(servico, mock_repositorio):
    dados = SolicitacaoProduto(nome="Produto X", descricao="Desc", link_produto="http://link.com")
    produto = Produto(produto_id=1, **dados.model_dump())
    mock_repositorio.salvar.return_value = produto

    resultado = servico.criar_produto(dados)
    mock_repositorio.salvar.assert_called_once()
    assert resultado.produto_id == 1


def test_listar_produtos(servico, mock_repositorio):
    servico.listar_produtos()
    mock_repositorio.buscar_todos.assert_called_once()


def test_buscar_produto_sucesso(servico, mock_repositorio):
    mock_repositorio.buscar_por_id.return_value = Produto(produto_id=1)
    resultado = servico.buscar_produto(1)
    assert resultado.produto_id == 1


def test_buscar_produto_nao_encontrado(servico, mock_repositorio):
    mock_repositorio.buscar_por_id.return_value = None
    with pytest.raises(ValueError, match="Produto não encontrado."):
        servico.buscar_produto(1)


def test_atualizar_produto_sucesso(servico, mock_repositorio):
    produto = Produto(produto_id=1, nome="Antigo")
    mock_repositorio.buscar_por_id.return_value = produto
    mock_repositorio.salvar.return_value = produto

    dados = SolicitacaoProduto(nome="Novo", descricao="Nova desc")
    resultado = servico.atualizar_produto(1, dados)
    mock_repositorio.salvar.assert_called_once()


def test_atualizar_produto_nao_encontrado(servico, mock_repositorio):
    mock_repositorio.buscar_por_id.return_value = None
    dados = SolicitacaoProduto(nome="Novo")

    with pytest.raises(ValueError, match="Produto não encontrado."):
        servico.atualizar_produto(1, dados)


def test_deletar_produto_sucesso(servico, mock_repositorio):
    produto = Produto(produto_id=1)
    mock_repositorio.buscar_por_id.return_value = produto
    servico.deletar_produto(1)
    mock_repositorio.deletar.assert_called_once_with(produto)


def test_deletar_produto_nao_encontrado(servico, mock_repositorio):
    mock_repositorio.buscar_por_id.return_value = None
    with pytest.raises(ValueError, match="Produto não encontrado."):
        servico.deletar_produto(1)


def test_deletar_produto_com_pedidos_e_recusado(
    servico, mock_repositorio, mock_repositorio_pedido
):
    """US21: historico de pedidos preservado — exclusao nao pode deixa-los orfaos."""
    produto = Produto(produto_id=1)
    mock_repositorio.buscar_por_id.return_value = produto
    mock_repositorio_pedido.contar_por_produto.return_value = 2

    with pytest.raises(ProdutoComPedidosError, match="possui pedidos registrados"):
        servico.deletar_produto(1)

    mock_repositorio_pedido.contar_por_produto.assert_called_once_with(1)
    mock_repositorio.deletar.assert_not_called()


def test_deletar_produto_sem_pedidos_consulta_a_contagem(
    servico, mock_repositorio, mock_repositorio_pedido
):
    produto = Produto(produto_id=1)
    mock_repositorio.buscar_por_id.return_value = produto

    servico.deletar_produto(1)

    mock_repositorio_pedido.contar_por_produto.assert_called_once_with(1)
    mock_repositorio.deletar.assert_called_once_with(produto)
