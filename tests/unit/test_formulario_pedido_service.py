"""Servico do fluxo de pedidos (US21)."""
from unittest.mock import MagicMock

import pytest

from src.formulario.service import ServicoFormulario


@pytest.fixture
def mock_repositorio():
    return MagicMock()


@pytest.fixture
def servico(mock_repositorio):
    return ServicoFormulario(repositorio=mock_repositorio)


def test_listar_pedidos_delega_ao_repositorio(servico, mock_repositorio):
    mock_db = MagicMock()
    mock_repositorio.listar_pedidos.return_value = []

    resultado = servico.listar_pedidos(mock_db, 1)

    mock_repositorio.listar_pedidos.assert_called_once_with(mock_db, 1)
    assert resultado == []


def test_fluxo_de_pedido_e_independente_dos_demais(servico, mock_repositorio):
    mock_db = MagicMock()

    servico.listar_pedidos(mock_db, 1)

    mock_repositorio.listar_inscricoes.assert_not_called()
    mock_repositorio.listar_participantes.assert_not_called()
