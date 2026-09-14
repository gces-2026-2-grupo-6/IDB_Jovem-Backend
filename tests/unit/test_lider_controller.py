import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

from src.lider.controller import (
    criar_lider, listar_lideres, listar_lideres_atuais, listar_diretores_anteriores,
    buscar_lider, atualizar_lider, deletar_lider, get_servico,
)


class TestLiderController:
    def test_get_servico(self):
        from src.lider.service import ServicoLider
        assert isinstance(get_servico(db=MagicMock()), ServicoLider)

    def test_criar_lider(self):
        mock_servico = MagicMock()
        criar_lider(solicitacao=MagicMock(), servico=mock_servico, _={})
        mock_servico.criar_lider.assert_called_once()

    def test_listar_lideres(self):
        mock_servico = MagicMock()
        listar_lideres(servico=mock_servico)
        mock_servico.listar_lideres.assert_called_once()

    def test_listar_lideres_atuais(self):
        mock_servico = MagicMock()
        listar_lideres_atuais(servico=mock_servico)
        mock_servico.listar_lideres_atuais.assert_called_once()

    def test_listar_diretores_anteriores(self):
        mock_servico = MagicMock()
        listar_diretores_anteriores(servico=mock_servico)
        mock_servico.listar_diretores_anteriores.assert_called_once()

    def test_buscar_lider_sucesso(self):
        mock_servico = MagicMock()
        buscar_lider(lider_id=1, servico=mock_servico)
        mock_servico.buscar_lider.assert_called_once_with(1)

    def test_buscar_lider_nao_encontrado(self):
        mock_servico = MagicMock()
        mock_servico.buscar_lider.side_effect = ValueError("Líder não encontrado.")
        with pytest.raises(HTTPException) as exc:
            buscar_lider(lider_id=1, servico=mock_servico)
        assert exc.value.status_code == 404

    def test_atualizar_lider_sucesso(self):
        mock_servico = MagicMock()
        atualizar_lider(lider_id=1, solicitacao=MagicMock(), servico=mock_servico, _={})
        mock_servico.atualizar_lider.assert_called_once()

    def test_atualizar_lider_nao_encontrado(self):
        mock_servico = MagicMock()
        mock_servico.atualizar_lider.side_effect = ValueError("Líder não encontrado.")
        with pytest.raises(HTTPException) as exc:
            atualizar_lider(lider_id=1, solicitacao=MagicMock(), servico=mock_servico, _={})
        assert exc.value.status_code == 404

    def test_deletar_lider_sucesso(self):
        mock_servico = MagicMock()
        deletar_lider(lider_id=1, servico=mock_servico, _={})
        mock_servico.deletar_lider.assert_called_once_with(1)

    def test_deletar_lider_nao_encontrado(self):
        mock_servico = MagicMock()
        mock_servico.deletar_lider.side_effect = ValueError("Líder não encontrado.")
        with pytest.raises(HTTPException) as exc:
            deletar_lider(lider_id=1, servico=mock_servico, _={})
        assert exc.value.status_code == 404
