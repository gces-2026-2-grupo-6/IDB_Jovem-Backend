import pytest
from unittest.mock import MagicMock

from src.lider.model import Lider
from src.lider.schema import SolicitacaoLider
from src.lider.service import ServicoLider
from tests.unit.lider_dados_teste import (
    lider_atual_brasileiro,
    diretor_anterior_brasileiro,
)


@pytest.fixture
def mock_repositorio():
    return MagicMock()


@pytest.fixture
def servico(mock_repositorio):
    return ServicoLider(repositorio=mock_repositorio)


def test_criar_lider_persiste_campos_de_perfil(servico, mock_repositorio):
    dados = SolicitacaoLider(
        nome="Ana Souza",
        cargo="Coordenadora Geral",
        regiao="Sudeste",
        mini_biografia="Bio curta.",
        redes_sociais={"instagram": "https://instagram.com/ana"},
    )
    mock_repositorio.salvar.side_effect = lambda lider: lider

    resultado = servico.criar_lider(dados)

    lider_salvo = mock_repositorio.salvar.call_args.args[0]
    assert isinstance(lider_salvo, Lider)
    assert lider_salvo.regiao == "Sudeste"
    assert lider_salvo.mini_biografia == "Bio curta."
    assert lider_salvo.redes_sociais == {"instagram": "https://instagram.com/ana"}
    assert lider_salvo.is_antigo is False
    assert resultado is lider_salvo


def test_listar_lideres(servico, mock_repositorio):
    mock_repositorio.buscar_todos.return_value = [lider_atual_brasileiro()]

    resultado = servico.listar_lideres()

    mock_repositorio.buscar_todos.assert_called_once()
    assert len(resultado) == 1


def test_listar_lideres_atuais(servico, mock_repositorio):
    mock_repositorio.buscar_lideres_atuais.return_value = [lider_atual_brasileiro()]

    resultado = servico.listar_lideres_atuais()

    mock_repositorio.buscar_lideres_atuais.assert_called_once()
    mock_repositorio.buscar_diretores_anteriores.assert_not_called()
    assert all(lider.is_antigo is False for lider in resultado)


def test_listar_diretores_anteriores(servico, mock_repositorio):
    mock_repositorio.buscar_diretores_anteriores.return_value = [diretor_anterior_brasileiro()]

    resultado = servico.listar_diretores_anteriores()

    mock_repositorio.buscar_diretores_anteriores.assert_called_once()
    mock_repositorio.buscar_lideres_atuais.assert_not_called()
    assert all(lider.is_antigo is True for lider in resultado)


def test_buscar_lider_sucesso(servico, mock_repositorio):
    mock_repositorio.buscar_por_id.return_value = lider_atual_brasileiro()

    assert servico.buscar_lider(1).lider_id == 1


def test_buscar_lider_nao_encontrado(servico, mock_repositorio):
    mock_repositorio.buscar_por_id.return_value = None

    with pytest.raises(ValueError, match="Líder não encontrado."):
        servico.buscar_lider(99)


def test_atualizar_lider_altera_campos_de_perfil(servico, mock_repositorio):
    lider = lider_atual_brasileiro()
    mock_repositorio.buscar_por_id.return_value = lider
    mock_repositorio.salvar.side_effect = lambda l: l

    dados = SolicitacaoLider(
        nome=lider.nome,
        cargo=lider.cargo,
        regiao="Centro-Oeste",
        mini_biografia="Nova bio.",
        redes_sociais={"youtube": "https://youtube.com/@ana"},
    )
    resultado = servico.atualizar_lider(1, dados)

    assert resultado.regiao == "Centro-Oeste"
    assert resultado.mini_biografia == "Nova bio."
    assert resultado.redes_sociais == {"youtube": "https://youtube.com/@ana"}
    mock_repositorio.salvar.assert_called_once_with(lider)


def test_atualizar_lider_preserva_campos_nao_enviados(servico, mock_repositorio):
    lider = diretor_anterior_brasileiro()
    redes_originais = dict(lider.redes_sociais)
    mock_repositorio.buscar_por_id.return_value = lider
    mock_repositorio.salvar.side_effect = lambda l: l

    resultado = servico.atualizar_lider(2, SolicitacaoLider(nome="Carlos P.", cargo=lider.cargo))

    assert resultado.nome == "Carlos P."
    assert resultado.regiao == "Nordeste"
    assert resultado.redes_sociais == redes_originais


def test_atualizar_lider_nao_muda_is_antigo_sozinho(servico, mock_repositorio):
    lider = diretor_anterior_brasileiro()
    mock_repositorio.buscar_por_id.return_value = lider
    mock_repositorio.salvar.side_effect = lambda l: l

    resultado = servico.atualizar_lider(2, SolicitacaoLider(nome=lider.nome, cargo="Outro cargo"))

    assert resultado.is_antigo is True


def test_atualizar_lider_permite_limpar_redes_sociais(servico, mock_repositorio):
    lider = lider_atual_brasileiro()
    mock_repositorio.buscar_por_id.return_value = lider
    mock_repositorio.salvar.side_effect = lambda l: l

    dados = SolicitacaoLider(nome=lider.nome, cargo=lider.cargo, redes_sociais=None)
    resultado = servico.atualizar_lider(1, dados)

    assert resultado.redes_sociais is None


def test_atualizar_lider_nao_encontrado(servico, mock_repositorio):
    mock_repositorio.buscar_por_id.return_value = None

    with pytest.raises(ValueError, match="Líder não encontrado."):
        servico.atualizar_lider(99, SolicitacaoLider(nome="Ana", cargo="Líder"))
    mock_repositorio.salvar.assert_not_called()


def test_deletar_lider_sucesso(servico, mock_repositorio):
    lider = lider_atual_brasileiro()
    mock_repositorio.buscar_por_id.return_value = lider

    servico.deletar_lider(1)

    mock_repositorio.deletar.assert_called_once_with(lider)


def test_deletar_lider_nao_encontrado(servico, mock_repositorio):
    mock_repositorio.buscar_por_id.return_value = None

    with pytest.raises(ValueError, match="Líder não encontrado."):
        servico.deletar_lider(99)
    mock_repositorio.deletar.assert_not_called()
