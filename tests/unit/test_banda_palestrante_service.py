import pytest
from unittest.mock import MagicMock
from sqlalchemy.exc import IntegrityError

from src.banda_palestrante.service import ConvidadoVinculadoError, ServicoBandaPalestrante
from src.banda_palestrante.model import BandaPalestrante
from src.banda_palestrante.schema import SolicitacaoBandaPalestrante


@pytest.fixture
def mock_repositorio():
    return MagicMock()


@pytest.fixture
def servico(mock_repositorio):
    return ServicoBandaPalestrante(repositorio=mock_repositorio)


def test_criar_banda_palestrante(servico, mock_repositorio):
    dados = SolicitacaoBandaPalestrante(nome="Banda X", link_foto="http://foto.com", profissao="Músico")
    participante = BandaPalestrante(participante_id=1, **dados.model_dump())
    mock_repositorio.salvar.return_value = participante

    resultado = servico.criar_banda_palestrante(dados)
    mock_repositorio.salvar.assert_called_once()
    assert resultado.participante_id == 1


def test_listar_banda_palestrantes(servico, mock_repositorio):
    servico.listar_banda_palestrantes()
    mock_repositorio.buscar_todos.assert_called_once()


def test_buscar_banda_palestrante_sucesso(servico, mock_repositorio):
    mock_repositorio.buscar_por_id.return_value = BandaPalestrante(participante_id=1)
    resultado = servico.buscar_banda_palestrante(1)
    assert resultado.participante_id == 1


def test_buscar_banda_palestrante_nao_encontrado(servico, mock_repositorio):
    mock_repositorio.buscar_por_id.return_value = None
    with pytest.raises(ValueError, match="Banda ou palestrante não encontrado."):
        servico.buscar_banda_palestrante(1)


def test_atualizar_banda_palestrante_sucesso(servico, mock_repositorio):
    participante = BandaPalestrante(participante_id=1, nome="Antigo", link_foto=None, profissao="Palestrante")
    mock_repositorio.buscar_por_id.return_value = participante
    mock_repositorio.atualizar.side_effect = lambda p: p

    dados = SolicitacaoBandaPalestrante(
        nome="Pr. André", link_foto="http://nova-foto.com", profissao="Palestrante"
    )
    resultado = servico.atualizar_banda_palestrante(1, dados)

    assert resultado.nome == "Pr. André"
    assert resultado.link_foto == "http://nova-foto.com"
    mock_repositorio.atualizar.assert_called_once_with(participante)


def test_atualizar_banda_palestrante_nao_encontrado(servico, mock_repositorio):
    mock_repositorio.buscar_por_id.return_value = None
    dados = SolicitacaoBandaPalestrante(nome="X", link_foto=None, profissao="Banda")
    with pytest.raises(ValueError, match="Banda ou palestrante não encontrado."):
        servico.atualizar_banda_palestrante(1, dados)


def test_deletar_banda_palestrante_sucesso(servico, mock_repositorio):
    participante = BandaPalestrante(participante_id=1)
    mock_repositorio.buscar_por_id.return_value = participante
    mock_repositorio.contar_eventos_vinculados.return_value = 0
    servico.deletar_banda_palestrante(1)
    mock_repositorio.deletar.assert_called_once_with(participante)


@pytest.mark.parametrize("vinculos, trecho", [(1, "1 evento."), (3, "3 eventos.")])
def test_deletar_convidado_vinculado_recusa_sem_apagar(servico, mock_repositorio, vinculos, trecho):
    mock_repositorio.buscar_por_id.return_value = BandaPalestrante(participante_id=1)
    mock_repositorio.contar_eventos_vinculados.return_value = vinculos
    with pytest.raises(ConvidadoVinculadoError, match=trecho):
        servico.deletar_banda_palestrante(1)
    mock_repositorio.deletar.assert_not_called()


def test_deletar_convidado_com_vinculo_concorrente_vira_conflito(servico, mock_repositorio):
    mock_repositorio.buscar_por_id.return_value = BandaPalestrante(participante_id=1)
    mock_repositorio.contar_eventos_vinculados.return_value = 0
    mock_repositorio.deletar.side_effect = IntegrityError("DELETE", {}, Exception("fk"))
    with pytest.raises(ConvidadoVinculadoError):
        servico.deletar_banda_palestrante(1)


def test_deletar_banda_palestrante_nao_encontrado(servico, mock_repositorio):
    mock_repositorio.buscar_por_id.return_value = None
    with pytest.raises(ValueError, match="Banda ou palestrante não encontrado."):
        servico.deletar_banda_palestrante(1)
