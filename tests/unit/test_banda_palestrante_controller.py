import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException
from src.banda_palestrante.controller import (
    criar_banda_palestrante, listar_banda_palestrantes,
    buscar_banda_palestrante, deletar_banda_palestrante, get_servico,
)
from src.banda_palestrante.service import ConvidadoVinculadoError


class TestBandaPalestranteController:
    def test_get_servico(self):
        mock_db = MagicMock()
        servico = get_servico(db=mock_db)
        from src.banda_palestrante.service import ServicoBandaPalestrante
        assert isinstance(servico, ServicoBandaPalestrante)

    def test_criar_banda_palestrante_sucesso(self):
        mock_servico = MagicMock()
        mock_servico.criar_banda_palestrante.return_value = MagicMock()
        resultado = criar_banda_palestrante(solicitacao=MagicMock(), servico=mock_servico, _={})
        mock_servico.criar_banda_palestrante.assert_called_once()

    def test_listar_banda_palestrantes(self):
        mock_servico = MagicMock()
        mock_servico.listar_banda_palestrantes.return_value = []
        resultado = listar_banda_palestrantes(servico=mock_servico)
        mock_servico.listar_banda_palestrantes.assert_called_once()

    def test_buscar_banda_palestrante_sucesso(self):
        mock_servico = MagicMock()
        mock_servico.buscar_banda_palestrante.return_value = MagicMock()
        resultado = buscar_banda_palestrante(participante_id=1, servico=mock_servico)
        mock_servico.buscar_banda_palestrante.assert_called_once_with(1)

    def test_buscar_banda_palestrante_nao_encontrado(self):
        mock_servico = MagicMock()
        mock_servico.buscar_banda_palestrante.side_effect = ValueError("Não encontrado")
        with pytest.raises(HTTPException) as exc:
            buscar_banda_palestrante(participante_id=1, servico=mock_servico)
        assert exc.value.status_code == 404

    def test_deletar_banda_palestrante_sucesso(self):
        mock_servico = MagicMock()
        deletar_banda_palestrante(participante_id=1, servico=mock_servico, _={})
        mock_servico.deletar_banda_palestrante.assert_called_once_with(1)

    def test_deletar_convidado_vinculado_responde_409(self):
        mock_servico = MagicMock()
        mock_servico.deletar_banda_palestrante.side_effect = ConvidadoVinculadoError("vinculado")
        with pytest.raises(HTTPException) as exc:
            deletar_banda_palestrante(participante_id=1, servico=mock_servico, _={})
        assert exc.value.status_code == 409
        assert exc.value.detail == "vinculado"

    def test_deletar_banda_palestrante_nao_encontrado(self):
        mock_servico = MagicMock()
        mock_servico.deletar_banda_palestrante.side_effect = ValueError("Não encontrado")
        with pytest.raises(HTTPException) as exc:
            deletar_banda_palestrante(participante_id=1, servico=mock_servico, _={})
        assert exc.value.status_code == 404
