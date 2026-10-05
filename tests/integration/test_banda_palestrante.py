import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from src.banda_palestrante.controller import router, get_servico
from src.security import obter_usuario_atual



USUARIO_ADMIN = {"sub": "uuid-admin", "realm_access": {"roles": ["admin", "superadmin"]}}


@pytest.fixture
def mock_servico():
    return MagicMock()


@pytest.fixture
def client(mock_servico):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_servico] = lambda: mock_servico
    app.dependency_overrides[obter_usuario_atual] = lambda: USUARIO_ADMIN
    with TestClient(app) as c:
        yield c, mock_servico
    app.dependency_overrides.clear()


BANDA_VALIDA = {
    "nome": "Banda Teste",
    "link_foto": "https://exemplo.com/foto.jpg",
    "profissao": "Palestrante",
}

RESPOSTA_BANDA = {**BANDA_VALIDA, "participante_id": 1}
BANDA_MINIMA = {"nome": "Só o Nome"}
RESPOSTA_BANDA_MINIMA = {**BANDA_MINIMA, "link_foto": None, "profissao": None, "participante_id": 2}



class TestCriarBandaPalestrante:

    def test_criar_com_todos_os_campos(self, client):
        c, servico = client
        servico.criar_banda_palestrante.return_value = RESPOSTA_BANDA
        resposta = c.post("/banda-palestrante/", json=BANDA_VALIDA)
        assert resposta.status_code == 201
        assert resposta.json()["nome"] == BANDA_VALIDA["nome"]
        servico.criar_banda_palestrante.assert_called_once()

    def test_criar_apenas_com_nome(self, client):
        c, servico = client
        servico.criar_banda_palestrante.return_value = RESPOSTA_BANDA_MINIMA
        resposta = c.post("/banda-palestrante/", json=BANDA_MINIMA)
        assert resposta.status_code == 201
        assert resposta.json()["link_foto"] is None
        assert resposta.json()["profissao"] is None

    def test_criar_sem_nome_retorna_422(self, client):
        c, _ = client
        payload = {"link_foto": "https://exemplo.com/foto.jpg", "profissao": "DJ"}
        resposta = c.post("/banda-palestrante/", json=payload)
        assert resposta.status_code == 422

    def test_criar_payload_vazio_retorna_422(self, client):
        c, _ = client
        resposta = c.post("/banda-palestrante/", json={})
        assert resposta.status_code == 422

class TestListarBandaPalestrantes:

    def test_listar_retorna_lista(self, client):
        c, servico = client
        servico.listar_banda_palestrantes.return_value = [RESPOSTA_BANDA]
        resposta = c.get("/banda-palestrante/")
        assert resposta.status_code == 200
        assert isinstance(resposta.json(), list)
        assert len(resposta.json()) == 1

    def test_listar_retorna_lista_vazia(self, client):
        c, servico = client
        servico.listar_banda_palestrantes.return_value = []
        resposta = c.get("/banda-palestrante/")
        assert resposta.status_code == 200
        assert resposta.json() == []

    def test_listar_nao_exige_autenticacao(self, client):
        c, servico = client
        servico.listar_banda_palestrantes.return_value = [RESPOSTA_BANDA]
        resposta = c.get("/banda-palestrante/")
        assert resposta.status_code == 200

    def test_listar_multiplos_participantes(self, client):
        c, servico = client
        participantes = [
            {**BANDA_VALIDA, "participante_id": i, "nome": f"Participante {i}"}
            for i in range(1, 5)
        ]
        servico.listar_banda_palestrantes.return_value = participantes
        resposta = c.get("/banda-palestrante/")
        assert len(resposta.json()) == 4



class TestBuscarBandaPalestrante:

    def test_buscar_existente(self, client):
        c, servico = client
        servico.buscar_banda_palestrante.return_value = RESPOSTA_BANDA
        resposta = c.get("/banda-palestrante/1")
        assert resposta.status_code == 200
        assert resposta.json()["participante_id"] == 1

    def test_buscar_nao_encontrado(self, client):
        c, servico = client
        servico.buscar_banda_palestrante.side_effect = ValueError("Não encontrado")
        resposta = c.get("/banda-palestrante/999")
        assert resposta.status_code == 404
        assert "Não encontrado" in resposta.json()["detail"]

class TestDeletarBandaPalestrante:

    def test_deletar_sucesso(self, client):
        c, servico = client
        servico.deletar_banda_palestrante.return_value = None
        resposta = c.delete("/banda-palestrante/1")
        assert resposta.status_code == 204
        servico.deletar_banda_palestrante.assert_called_once_with(1)

    def test_deletar_nao_encontrado(self, client):
        c, servico = client
        servico.deletar_banda_palestrante.side_effect = ValueError("Participante não encontrado")
        resposta = c.delete("/banda-palestrante/999")
        assert resposta.status_code == 404
        assert "Participante não encontrado" in resposta.json()["detail"]
