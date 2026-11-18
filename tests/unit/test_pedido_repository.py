import pytest
from unittest.mock import MagicMock

from src.pedido.repository import RepositorioPedido
from src.pedido.model import Pedido


@pytest.fixture
def mock_db_session():
    return MagicMock()


@pytest.fixture
def repositorio(mock_db_session):
    return RepositorioPedido(db=mock_db_session)


def test_salvar(repositorio, mock_db_session):
    pedido = Pedido(
        produto_id=1, nome_solicitante="Ana", contato_solicitante="ana@exemplo.org"
    )
    resultado = repositorio.salvar(pedido)
    mock_db_session.add.assert_called_once_with(pedido)
    mock_db_session.commit.assert_called_once()
    assert resultado == pedido


def test_buscar_por_id(repositorio, mock_db_session):
    repositorio.buscar_por_id(1)
    mock_db_session.query.assert_called_with(Pedido)
    mock_db_session.query().filter().first.assert_called_once()


def test_buscar_todos_com_produto(repositorio, mock_db_session):
    repositorio.buscar_todos_com_produto()
    mock_db_session.query().join().order_by().all.assert_called_once()


def test_buscar_todos_com_produto_vazio(repositorio, mock_db_session):
    mock_db_session.query.return_value.join.return_value.order_by.return_value.all.return_value = []
    assert repositorio.buscar_todos_com_produto() == []


def test_buscar_por_id_com_produto(repositorio, mock_db_session):
    repositorio.buscar_por_id_com_produto(1)
    mock_db_session.query().join().filter().first.assert_called_once()


def test_buscar_por_id_com_produto_nao_encontrado(repositorio, mock_db_session):
    mock_db_session.query.return_value.join.return_value.filter.return_value.first.return_value = None
    assert repositorio.buscar_por_id_com_produto(999) is None


def test_contar_por_produto(repositorio, mock_db_session):
    repositorio.contar_por_produto(1)
    mock_db_session.query.assert_called_with(Pedido)
    mock_db_session.query().filter().count.assert_called_once()


def test_contar_por_produto_sem_pedidos(repositorio, mock_db_session):
    mock_db_session.query.return_value.filter.return_value.count.return_value = 0
    assert repositorio.contar_por_produto(1) == 0
