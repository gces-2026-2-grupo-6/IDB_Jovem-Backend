import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from src.auth.controller import iniciar_login, callback_google


class TestAuthController:
    @patch("src.auth.controller.ServicoAuth")
    def test_iniciar_login(self, mock_auth_class):
        mock_auth = MagicMock()
        mock_auth.gerar_url_login.return_value = ("http://google.com/auth", "state-123", "verifier-123")
        mock_auth_class.return_value = mock_auth

        mock_request = MagicMock()
        mock_request.session = {}

        resultado = iniciar_login(request=mock_request)
        assert resultado.status_code == 307  # RedirectResponse

    @patch("src.auth.controller.ServicoAuth")
    def test_callback_google_sucesso(self, mock_auth_class):
        mock_auth = MagicMock()
        mock_auth.trocar_codigo_por_tokens.return_value = {
            "access_token": "at-123",
            "refresh_token": "rt-456",
        }
        mock_auth_class.return_value = mock_auth

        mock_request = MagicMock()
        mock_request.session = {
            "google_estado": "state-123",
            "google_verificador_codigo": "verifier-123",
        }

        resultado = callback_google(request=mock_request, codigo="code-123")
        assert "mensagem" in resultado
        # A resposta confirma o login e diz onde buscar o refresh token, sem
        # carregar token nenhum: ver _guardar_refresh_token em
        # src/auth/controller.py e os testes de
        # tests/unit/test_achados_exploratorios.py.
        assert resultado["recebeu_refresh_token"] is True
        assert "at-123" not in str(resultado)
        assert "rt-456" not in str(resultado)

    def test_callback_google_sessao_expirada(self):
        mock_request = MagicMock()
        mock_request.session = {}

        with pytest.raises(HTTPException) as exc:
            callback_google(request=mock_request, codigo="code-123")
        assert exc.value.status_code == 400

    def test_callback_google_sem_verificador(self):
        mock_request = MagicMock()
        mock_request.session = {"google_estado": "state-123"}

        with pytest.raises(HTTPException) as exc:
            callback_google(request=mock_request, codigo="code-123")
        assert exc.value.status_code == 400
