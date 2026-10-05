import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from src.formulario.controller import router, get_servico
from src.security import obter_usuario_atual

USUARIO_INSCRICOES = {"realm_access": {"roles": ["admin", "admin-inscricoes"]}}



@pytest.fixture
def mock_servico():
    return MagicMock()


@pytest.fixture
def client(mock_servico):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_servico] = lambda: mock_servico
    app.dependency_overrides[obter_usuario_atual] = lambda: USUARIO_INSCRICOES
    with TestClient(app) as c:
        yield c, mock_servico
    app.dependency_overrides.clear()


@pytest.fixture
def app_sem_override_de_usuario(mock_servico):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_servico] = lambda: mock_servico
    yield app
    app.dependency_overrides.clear()


class TestAutorizacaoInscricoes:
    """
    A lista devolve nome e e-mail de cada inscrito e grava voluntarios no
    banco. Ate a Sprint 2 era publica: qualquer pessoa podia enumerar os
    inscritos de todos os eventos pelo id.
    """

    def test_sem_token_e_negado(self, app_sem_override_de_usuario, mock_servico):
        with TestClient(app_sem_override_de_usuario) as c:
            resposta = c.get("/formulario/eventos/1/inscricoes")
        assert resposta.status_code in (401, 403)
        mock_servico.listar_inscricoes.assert_not_called()

    def test_admin_de_outro_setor_e_negado(self, app_sem_override_de_usuario, mock_servico):
        app_sem_override_de_usuario.dependency_overrides[obter_usuario_atual] = (
            lambda: {"realm_access": {"roles": ["admin", "admin-eventos"]}}
        )
        with TestClient(app_sem_override_de_usuario) as c:
            resposta = c.get("/formulario/eventos/1/inscricoes")
        assert resposta.status_code == 403
        mock_servico.listar_inscricoes.assert_not_called()




INSCRICAO_RESPOSTA = {
    "voluntario_id": 1,
    "status": "confirmado",
    "resposta_id": "resp-001",
    "link_resposta": "https://forms.google.com/resp/001",
    "nome": "João Silva",
    "email": "joao@teste.com",
    "evento_id": 1,
}



class TestListarInscricoes:

    def test_listar_inscricoes_sucesso(self, client):
        c, servico = client
        servico.listar_inscricoes.return_value = [INSCRICAO_RESPOSTA]
        resposta = c.get("/formulario/eventos/1/inscricoes")
        assert resposta.status_code == 200
        assert isinstance(resposta.json(), list)
        assert len(resposta.json()) == 1

    def test_listar_inscricoes_lista_vazia(self, client):
        c, servico = client
        servico.listar_inscricoes.return_value = []
        resposta = c.get("/formulario/eventos/1/inscricoes")
        assert resposta.status_code == 200
        assert resposta.json() == []

    def test_listar_inscricoes_evento_nao_encontrado(self, client):
        c, servico = client
        servico.listar_inscricoes.side_effect = ValueError("Evento não encontrado")
        resposta = c.get("/formulario/eventos/999/inscricoes")
        assert resposta.status_code == 404
        assert "Evento não encontrado" in resposta.json()["detail"]

    def test_listar_inscricoes_erro_google_retorna_502(self, client):
        c, servico = client
        servico.listar_inscricoes.side_effect = RuntimeError(
            "Falha ao acessar Google Forms"
        )
        resposta = c.get("/formulario/eventos/1/inscricoes")
        assert resposta.status_code == 502
        assert "Falha ao acessar Google Forms" in resposta.json()["detail"]

    def test_listar_inscricoes_chama_servico_com_parametros_corretos(self, client):
        c, servico = client
        servico.listar_inscricoes.return_value = []
        c.get("/formulario/eventos/42/inscricoes")
        args, _ = servico.listar_inscricoes.call_args
        assert args[1] == 42

    def test_listar_inscricoes_multiplas(self, client):
        c, servico = client
        inscricoes = [
            {**INSCRICAO_RESPOSTA, "nome": f"Pessoa {i}", "email": f"pessoa{i}@teste.com"}
            for i in range(1, 5)
        ]
        servico.listar_inscricoes.return_value = inscricoes
        resposta = c.get("/formulario/eventos/1/inscricoes")
        assert resposta.status_code == 200
        assert len(resposta.json()) == 4