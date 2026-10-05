"""Servico do fluxo de participantes (US09)."""
from unittest.mock import MagicMock

import pytest

from src.formulario.service import ServicoFormulario


@pytest.fixture
def mock_repositorio():
    return MagicMock()


@pytest.fixture
def servico(mock_repositorio):
    return ServicoFormulario(repositorio=mock_repositorio)


def test_listar_participantes_delega_ao_repositorio(servico, mock_repositorio):
    mock_db = MagicMock()
    mock_repositorio.listar_participantes.return_value = []

    resultado = servico.listar_participantes(mock_db, 1)

    mock_repositorio.listar_participantes.assert_called_once_with(mock_db, 1)
    assert resultado == []


def test_os_dois_fluxos_sao_independentes(servico, mock_repositorio):
    mock_db = MagicMock()

    servico.listar_participantes(mock_db, 1)

    mock_repositorio.listar_inscricoes.assert_not_called()
