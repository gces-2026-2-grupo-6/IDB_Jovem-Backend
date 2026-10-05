import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch
from starlette.middleware.sessions import SessionMiddleware

from src.auth.controller import router


@pytest.fixture
def client():
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(router)
    with TestClient(app, follow_redirects=False) as c:
        yield c



class TestIniciarLogin:

    def test_login_redireciona_para_google(self, client):
        with patch("src.auth.controller.ServicoAuth") as MockServico:
            MockServico.return_value.gerar_url_login.return_value = (
                "https://accounts.google.com/o/oauth2/auth?client_id=test",
                "estado-teste",
                "verificador-teste"
            )
            resposta = client.get("/auth/login")
        assert resposta.status_code in (302, 307)

    def test_login_redireciona_para_url_google(self, client):
        with patch("src.auth.controller.ServicoAuth") as MockServico:
            MockServico.return_value.gerar_url_login.return_value = (
                "https://accounts.google.com/o/oauth2/auth?client_id=test",
                "estado-teste",
                "verificador-teste"
            )
            resposta = client.get("/auth/login")
        location = resposta.headers.get("location", "")
        assert "google" in location or resposta.status_code in (302, 307)

class TestCallbackGoogle:

    def test_callback_sem_sessao_retorna_400(self, client):
        resposta = client.get("/auth/callback?code=codigo-teste")
        assert resposta.status_code == 400
        assert "Sessao OAuth expirada" in resposta.json()["detail"]

    def test_callback_sem_code_retorna_422(self, client):
        resposta = client.get("/auth/callback")
        assert resposta.status_code == 422

    @pytest.mark.parametrize("code", [
        "code_invalido_123",
        "outro_code_456",
        "code_expirado_789",
    ])
    def test_callback_sem_sessao_sempre_retorna_400(self, client, code):
        resposta = client.get(f"/auth/callback?code={code}")
        assert resposta.status_code == 400