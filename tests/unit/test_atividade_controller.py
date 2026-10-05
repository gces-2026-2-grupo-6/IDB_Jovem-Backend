import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException
from src.atividade.controller import (
    criar_atividade, buscar_todas_atividades, buscar_atividade_id,
    atualizar_atividade, deletar_atividade, get_servico,
)


class TestAtividadeController:
    def test_get_servico(self):
        mock_db = MagicMock()
        servico = get_servico(db=mock_db)
        from src.atividade.service import ServicoAtividade
        assert isinstance(servico, ServicoAtividade)

    def test_criar_atividade_sucesso(self):
        mock_servico = MagicMock()
        mock_servico.criar_atividade.return_value = MagicMock()
        resultado = criar_atividade(evento_id=1, solicitar=MagicMock(), servico=mock_servico, _={})
        mock_servico.criar_atividade.assert_called_once()

    def test_criar_atividade_erro(self):
        mock_servico = MagicMock()
        mock_servico.criar_atividade.side_effect = ValueError("Evento não encontrado")
        with pytest.raises(HTTPException) as exc:
            criar_atividade(evento_id=1, solicitar=MagicMock(), servico=mock_servico, _={})
        assert exc.value.status_code == 400

    def test_buscar_todas_atividades(self):
        mock_servico = MagicMock()
        mock_servico.listar_atividades.return_value = []
        resultado = buscar_todas_atividades(evento_id=1, servico=mock_servico)
        mock_servico.listar_atividades.assert_called_once_with(1)

    def test_buscar_atividade_id_sucesso(self):
        mock_servico = MagicMock()
        mock_servico.buscar_atividade.return_value = MagicMock()
        resultado = buscar_atividade_id(atividade_id=1, servico=mock_servico)
        mock_servico.buscar_atividade.assert_called_once_with(1)

    def test_buscar_atividade_id_nao_encontrada(self):
        mock_servico = MagicMock()
        mock_servico.buscar_atividade.side_effect = ValueError("Não encontrada")
        with pytest.raises(HTTPException) as exc:
            buscar_atividade_id(atividade_id=1, servico=mock_servico)
        assert exc.value.status_code == 404

    def test_atualizar_atividade_sucesso(self):
        mock_servico = MagicMock()
        mock_servico.atualizar_atividade.return_value = MagicMock()
        resultado = atualizar_atividade(atividade_id=1, solicitar=MagicMock(), servico=mock_servico, _={})
        mock_servico.atualizar_atividade.assert_called_once()

    def test_atualizar_atividade_erro(self):
        mock_servico = MagicMock()
        mock_servico.atualizar_atividade.side_effect = ValueError("Erro")
        with pytest.raises(HTTPException) as exc:
            atualizar_atividade(atividade_id=1, solicitar=MagicMock(), servico=mock_servico, _={})
        assert exc.value.status_code == 400

    def test_deletar_atividade_sucesso(self):
        mock_servico = MagicMock()
        deletar_atividade(atividade_id=1, servico=mock_servico, _={})
        mock_servico.deletar_atividade.assert_called_once_with(1)

    def test_deletar_atividade_erro(self):
        mock_servico = MagicMock()
        mock_servico.deletar_atividade.side_effect = ValueError("Não encontrada")
        with pytest.raises(HTTPException) as exc:
            deletar_atividade(atividade_id=1, servico=mock_servico, _={})
        assert exc.value.status_code == 404
