import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from src.admin.controller import router, get_servico
from src.security import obter_usuario_atual



USUARIO_SUPERADMIN = {"sub": "uuid-superadmin", "realm_access": {"roles": ["superadmin"]}}
USUARIO_ADMIN = {"sub": "uuid-admin", "realm_access": {"roles": ["admin", "superadmin"]}}


@pytest.fixture
def mock_servico():
    return MagicMock()


@pytest.fixture
def client(mock_servico):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_servico] = lambda: mock_servico
    app.dependency_overrides[obter_usuario_atual] = lambda: USUARIO_SUPERADMIN
    with TestClient(app) as c:
        yield c, mock_servico
    app.dependency_overrides.clear()



ADMIN_VALIDO = {
    "nome": "Admin Teste",
    "email": "admin@teste.com",
    "keycloak_id": "kc-uuid-001",
}

RESPOSTA_ADMIN = {**ADMIN_VALIDO, "admin_id": 1}



class TestCriarAdmin:

    def test_criar_admin_sucesso(self, client):
        c, servico = client
        servico.criar_admin.return_value = RESPOSTA_ADMIN
        resposta = c.post("/admin/", json=ADMIN_VALIDO)
        assert resposta.status_code == 201
        assert resposta.json()["email"] == ADMIN_VALIDO["email"]
        servico.criar_admin.assert_called_once()

    def test_criar_admin_email_duplicado(self, client):
        c, servico = client
        servico.criar_admin.side_effect = ValueError("Email já cadastrado")
        resposta = c.post("/admin/", json=ADMIN_VALIDO)
        assert resposta.status_code == 400
        assert "Email já cadastrado" in resposta.json()["detail"]

    @pytest.mark.parametrize("campo_ausente", ["nome", "email", "keycloak_id"])
    def test_criar_admin_campo_obrigatorio_ausente(self, client, campo_ausente):
        c, _ = client
        payload = {k: v for k, v in ADMIN_VALIDO.items() if k != campo_ausente}
        resposta = c.post("/admin/", json=payload)
        assert resposta.status_code == 422

    def test_criar_admin_email_invalido(self, client):
        c, _ = client
        payload = {**ADMIN_VALIDO, "email": "nao-e-um-email"}
        resposta = c.post("/admin/", json=payload)
        assert resposta.status_code == 422



class TestListarAdmins:

    def test_listar_admins_retorna_lista(self, client):
        c, servico = client
        servico.listar_admins.return_value = [RESPOSTA_ADMIN]
        resposta = c.get("/admin/")
        assert resposta.status_code == 200
        assert isinstance(resposta.json(), list)
        assert len(resposta.json()) == 1

    def test_listar_admins_lista_vazia(self, client):
        c, servico = client
        servico.listar_admins.return_value = []
        resposta = c.get("/admin/")
        assert resposta.status_code == 200
        assert resposta.json() == []

    def test_listar_admins_multiplos(self, client):
        c, servico = client
        admins = [
            {**ADMIN_VALIDO, "admin_id": i, "email": f"admin{i}@teste.com"}
            for i in range(1, 4)
        ]
        servico.listar_admins.return_value = admins
        resposta = c.get("/admin/")
        assert resposta.status_code == 200
        assert len(resposta.json()) == 3



class TestBuscarAdmin:

    def test_buscar_admin_existente(self, client):
        c, servico = client
        servico.buscar_admin.return_value = RESPOSTA_ADMIN
        resposta = c.get("/admin/1")
        assert resposta.status_code == 200
        assert resposta.json()["admin_id"] == 1

    def test_buscar_admin_nao_encontrado(self, client):
        c, servico = client
        servico.buscar_admin.side_effect = ValueError("Admin não encontrado")
        resposta = c.get("/admin/999")
        assert resposta.status_code == 404
        assert "Admin não encontrado" in resposta.json()["detail"]

class TestDeletarAdmin:

    def test_deletar_admin_sucesso(self, client):
        c, servico = client
        servico.deletar_admin.return_value = None
        resposta = c.delete("/admin/1")
        assert resposta.status_code == 204
        servico.deletar_admin.assert_called_once()

    def test_deletar_admin_nao_encontrado(self, client):
        c, servico = client
        servico.deletar_admin.side_effect = ValueError("Admin não encontrado")
        resposta = c.delete("/admin/999")
        assert resposta.status_code == 400

    def test_deletar_admin_propria_conta(self, client):
        c, servico = client
        servico.deletar_admin.side_effect = ValueError("Não é possível deletar a própria conta")
        resposta = c.delete("/admin/1")
        assert resposta.status_code == 400
        assert "própria conta" in resposta.json()["detail"]