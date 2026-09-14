"""
Testes da matriz de autorização por setor (US03 / RF01).
Valida que o servidor rejeita com 403 Forbidden ações fora do setor do administrador
e restringe exclusões e gestão de administradores exclusivamente ao superadmin.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.main import app
from src.security import obter_usuario_atual
from src.database import obter_banco
from src.evento.schema import RespostaEvento


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.query.return_value.all.return_value = []
    def mock_salvar(item):
        if hasattr(item, "produto_id") and not item.produto_id:
            item.produto_id = 1
        return item
    db.add.side_effect = mock_salvar
    return db


@pytest.fixture
def client(mock_db):
    app.dependency_overrides[obter_banco] = lambda: mock_db
    with patch("src.calendario.service.ServicoCalendario._obter_token_valido", return_value=None):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()


def usuario_mock(roles: list[str], sub: str = "usr-123"):
    return lambda: {
        "sub": sub,
        "realm_access": {"roles": roles},
    }



class TestMatrizAutorizacaoSetores:
    # 1. Setor Loja e Produtos
    def test_admin_produtos_pode_criar_produto(self, client):
        app.dependency_overrides[obter_usuario_atual] = usuario_mock(["admin", "admin-produtos"])
        payload = {"nome": "Camiseta IDB", "descricao": "Camiseta oficial"}
        resposta = client.post("/produto/", json=payload)
        # Não pode ser 403 Forbidden
        assert resposta.status_code != 403

    def test_admin_eventos_nao_pode_criar_produto(self, client):
        app.dependency_overrides[obter_usuario_atual] = usuario_mock(["admin", "admin-eventos"])
        payload = {"nome": "Camiseta IDB", "descricao": "Camiseta oficial"}
        resposta = client.post("/produto/", json=payload)
        assert resposta.status_code == 403
        assert "produtos" in resposta.json()["detail"]

    def test_admin_produtos_nao_pode_deletar_produto(self, client):
        app.dependency_overrides[obter_usuario_atual] = usuario_mock(["admin", "admin-produtos"])
        resposta = client.delete("/produto/1")
        assert resposta.status_code == 403

    # 2. Setor Agenda e Eventos
    def test_admin_eventos_pode_criar_evento(self, client):
        app.dependency_overrides[obter_usuario_atual] = usuario_mock(["admin", "admin-eventos"])
        payload = {
            "nome": "Congresso 2026",
            "tipo_evento": "Conferência",
            "local_latitude": -15.7801,
            "local_longitude": -47.9292,
            "data_inicio": "2026-10-10T10:00:00Z",
            "data_fim": "2026-10-12T22:00:00Z",
        }
        with patch("src.evento.service.ServicoEvento.criar_evento") as mock_criar:
            mock_criar.return_value = RespostaEvento(
                **payload, evento_id=1, calendario_evento_id=None, nome_local=None
            )
            resposta = client.post("/evento/", json=payload)
            assert resposta.status_code == 201

    def test_admin_produtos_nao_pode_criar_evento(self, client):
        app.dependency_overrides[obter_usuario_atual] = usuario_mock(["admin", "admin-produtos"])
        payload = {
            "nome": "Congresso 2026",
            "tipo_evento": "Conferência",
            "local_latitude": -15.7801,
            "local_longitude": -47.9292,
            "data_inicio": "2026-10-10T10:00:00Z",
            "data_fim": "2026-10-12T22:00:00Z",
        }
        resposta = client.post("/evento/", json=payload)
        assert resposta.status_code == 403
        assert "eventos" in resposta.json()["detail"]

    def test_admin_eventos_nao_pode_deletar_evento(self, client):
        app.dependency_overrides[obter_usuario_atual] = usuario_mock(["admin", "admin-eventos"])
        resposta = client.delete("/evento/1")
        assert resposta.status_code == 403

    def test_admin_eventos_nao_pode_remover_participante_evento(self, client):
        app.dependency_overrides[obter_usuario_atual] = usuario_mock(["admin", "admin-eventos"])
        resposta = client.delete("/evento/1/participantes/1")
        assert resposta.status_code == 403

    # 3. Setor Inscrições / Voluntários
    def test_admin_inscricoes_pode_listar_voluntarios(self, client):
        app.dependency_overrides[obter_usuario_atual] = usuario_mock(["admin", "admin-inscricoes"])
        resposta = client.get("/voluntarios/")
        assert resposta.status_code != 403

    def test_admin_produtos_nao_pode_listar_voluntarios(self, client):
        app.dependency_overrides[obter_usuario_atual] = usuario_mock(["admin", "admin-produtos"])
        resposta = client.get("/voluntarios/")
        assert resposta.status_code == 403
        assert "inscricoes" in resposta.json()["detail"]

    def test_admin_inscricoes_nao_pode_deletar_voluntario(self, client):
        app.dependency_overrides[obter_usuario_atual] = usuario_mock(["admin", "admin-inscricoes"])
        resposta = client.delete("/voluntarios/1")
        assert resposta.status_code == 403

    # 4. Exclusão de Líder
    def test_admin_comum_nao_pode_deletar_lider(self, client):
        app.dependency_overrides[obter_usuario_atual] = usuario_mock(["admin", "admin-eventos"])
        resposta = client.delete("/lider/1")
        assert resposta.status_code == 403

    def test_superadmin_pode_deletar_lider(self, client):
        app.dependency_overrides[obter_usuario_atual] = usuario_mock(["admin", "superadmin"])
        resposta = client.delete("/lider/1")
        assert resposta.status_code != 403

    # 5. Superadministrador tem acesso irrestrito e exclusão permitida
    def test_superadmin_pode_deletar_produto(self, client):
        app.dependency_overrides[obter_usuario_atual] = usuario_mock(["admin", "superadmin"])
        resposta = client.delete("/produto/1")
        # 404 (recurso inexistente no mock) ou 204, mas NUNCA 403
        assert resposta.status_code != 403

    def test_superadmin_pode_deletar_evento(self, client):
        app.dependency_overrides[obter_usuario_atual] = usuario_mock(["admin", "superadmin"])
        resposta = client.delete("/evento/1")
        assert resposta.status_code != 403

    def test_superadmin_pode_remover_participante_evento(self, client):
        app.dependency_overrides[obter_usuario_atual] = usuario_mock(["admin", "superadmin"])
        resposta = client.delete("/evento/1/participantes/1")
        assert resposta.status_code != 403

    def test_superadmin_pode_gerenciar_administradores(self, client):
        app.dependency_overrides[obter_usuario_atual] = usuario_mock(["admin", "superadmin"])
        resposta = client.get("/admin/")
        assert resposta.status_code != 403

    def test_admin_comum_nao_pode_gerenciar_administradores(self, client):
        app.dependency_overrides[obter_usuario_atual] = usuario_mock(["admin", "admin-eventos"])
        resposta = client.get("/admin/")
        assert resposta.status_code == 403
