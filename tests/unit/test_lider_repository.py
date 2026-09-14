import pytest
from unittest.mock import MagicMock

from src.lider.model import Lider
from src.lider.repository import RepositorioLider
from tests.unit.lider_dados_teste import (
    lider_atual_brasileiro,
    diretor_anterior_brasileiro,
    diretor_anterior_estrangeiro,
)


@pytest.fixture
def mock_db_session():
    return MagicMock()


@pytest.fixture
def repositorio(mock_db_session):
    return RepositorioLider(db=mock_db_session)


def test_salvar(repositorio, mock_db_session):
    lider = lider_atual_brasileiro()
    resultado = repositorio.salvar(lider)
    mock_db_session.add.assert_called_once_with(lider)
    mock_db_session.commit.assert_called_once()
    assert resultado == lider


def test_buscar_todos_ordena_por_ordem_e_lider_id(repositorio, mock_db_session):
    repositorio.buscar_todos()
    mock_db_session.query.assert_called_with(Lider)
    mock_db_session.query().order_by.assert_called_with(Lider.ordem, Lider.lider_id)
    mock_db_session.query().order_by().all.assert_called_once()


def test_buscar_lideres_atuais_filtra_is_antigo_false(repositorio, mock_db_session):
    repositorio.buscar_lideres_atuais()
    mock_db_session.query.assert_called_with(Lider)
    mock_db_session.query().filter().order_by.assert_called_with(
        Lider.ordem, Lider.lider_id
    )


def test_buscar_diretores_anteriores_filtra_is_antigo_true(repositorio, mock_db_session):
    repositorio.buscar_diretores_anteriores()
    mock_db_session.query.assert_called_with(Lider)
    mock_db_session.query().filter().order_by.assert_called_with(
        Lider.ordem, Lider.lider_id
    )


def test_buscar_por_id(repositorio, mock_db_session):
    repositorio.buscar_por_id(1)
    mock_db_session.query.assert_called_with(Lider)
    mock_db_session.query().filter().first.assert_called_once()


def test_deletar(repositorio, mock_db_session):
    lider = diretor_anterior_brasileiro()
    repositorio.deletar(lider)
    mock_db_session.delete.assert_called_once_with(lider)
    mock_db_session.commit.assert_called_once()


def test_dados_de_exemplo_cobrem_perfil_completo():
    atual = lider_atual_brasileiro()
    anterior_br = diretor_anterior_brasileiro()
    anterior_estrangeiro = diretor_anterior_estrangeiro()

    assert atual.is_antigo is False
    assert anterior_br.is_antigo is True
    assert anterior_estrangeiro.is_antigo is True

    for lider in (atual, anterior_br, anterior_estrangeiro):
        assert lider.regiao
        assert lider.mini_biografia
        assert lider.redes_sociais
