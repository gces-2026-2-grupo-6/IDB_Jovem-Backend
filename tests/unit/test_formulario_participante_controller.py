"""Controller do fluxo de participantes (US09)."""
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from src.formulario.controller import listar_participantes


class TestListarParticipantesController:
    def test_sucesso(self):
        mock_servico = MagicMock()
        mock_servico.listar_participantes.return_value = []
        mock_db = MagicMock()

        resultado = listar_participantes(evento_id=1, db=mock_db, servico=mock_servico)

        mock_servico.listar_participantes.assert_called_once_with(mock_db, 1)
        assert resultado == []

    def test_evento_sem_formulario_vira_404(self):
        mock_servico = MagicMock()
        mock_servico.listar_participantes.side_effect = ValueError(
            "Evento sem formulario de participantes configurado"
        )

        with pytest.raises(HTTPException) as exc:
            listar_participantes(evento_id=1, db=MagicMock(), servico=mock_servico)

        assert exc.value.status_code == 404

    def test_falha_do_google_vira_502(self):
        mock_servico = MagicMock()
        mock_servico.listar_participantes.side_effect = RuntimeError("Erro API")

        with pytest.raises(HTTPException) as exc:
            listar_participantes(evento_id=1, db=MagicMock(), servico=mock_servico)

        assert exc.value.status_code == 502
