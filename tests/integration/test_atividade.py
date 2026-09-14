import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from src.atividade.controller import router, get_servico
from src.security import obter_usuario_atual


USUARIO_ADMIN = {"sub": "user-123", "realm_access": {"roles": ["admin", "superadmin"]}}


@pytest.fixture
def mock_servico():
    return MagicMock()


@pytest.fixture
def client(mock_servico):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_servico] = lambda: mock_servico
    app.dependency_overrides[obter_usuario_atual] = lambda: USUARIO_ADMIN
    return TestClient(app)



ATIVIDADE_VALIDA = {
    "nome": "Palestra Principal",
    "descricao": "Descrição da palestra",
    "horario_inicio": "2025-06-01T09:00:00",
    "horario_termino": "2025-06-01T10:00:00",
}

RESPOSTA_ATIVIDADE = {**ATIVIDADE_VALIDA, "atividade_id": 1, "evento_id": 1}

ATIVIDADE_MINIMA = {
    "nome": "Atividade Simples",
    "horario_inicio": "2025-06-01T14:00:00",
    "horario_termino": "2025-06-01T15:00:00",
}

RESPOSTA_ATIVIDADE_MINIMA = {**ATIVIDADE_MINIMA, "descricao": None, "atividade_id": 2, "evento_id": 1}



class TestCriarAtividade:

    def test_criar_atividade_sucesso(self, client, mock_servico):
        mock_servico.criar_atividade.return_value = RESPOSTA_ATIVIDADE
        resposta = client.post("/evento/1/atividade", json=ATIVIDADE_VALIDA)
        assert resposta.status_code == 201
        assert resposta.json()["nome"] == ATIVIDADE_VALIDA["nome"]
        assert resposta.json()["evento_id"] == 1
        mock_servico.criar_atividade.assert_called_once()

    def test_criar_atividade_sem_descricao(self, client, mock_servico):
        mock_servico.criar_atividade.return_value = RESPOSTA_ATIVIDADE_MINIMA
        resposta = client.post("/evento/1/atividade", json=ATIVIDADE_MINIMA)
        assert resposta.status_code == 201
        assert resposta.json()["descricao"] is None

    def test_criar_atividade_evento_inexistente(self, client, mock_servico):
        mock_servico.criar_atividade.side_effect = ValueError("Evento não encontrado")
        resposta = client.post("/evento/999/atividade", json=ATIVIDADE_VALIDA)
        assert resposta.status_code == 400
        assert "Evento não encontrado" in resposta.json()["detail"]

    def test_criar_atividade_horario_invalido(self, client, mock_servico):
        mock_servico.criar_atividade.side_effect = ValueError("Horário inválido")
        resposta = client.post("/evento/1/atividade", json=ATIVIDADE_VALIDA)
        assert resposta.status_code == 400

    @pytest.mark.parametrize("campo_ausente", ["nome", "horario_inicio", "horario_termino"])
    def test_criar_atividade_campo_obrigatorio_ausente(self, client, mock_servico, campo_ausente):
        payload = {k: v for k, v in ATIVIDADE_VALIDA.items() if k != campo_ausente}
        resposta = client.post("/evento/1/atividade", json=payload)
        assert resposta.status_code == 422

    @pytest.mark.parametrize("evento_id", [1, 2, 10])
    def test_criar_atividade_varios_eventos(self, client, mock_servico, evento_id):
        mock_servico.criar_atividade.return_value = {**RESPOSTA_ATIVIDADE, "evento_id": evento_id}
        resposta = client.post(f"/evento/{evento_id}/atividade", json=ATIVIDADE_VALIDA)
        assert resposta.status_code == 201
        assert resposta.json()["evento_id"] == evento_id



class TestListarAtividades:

    def test_listar_atividades_de_evento(self, client, mock_servico):
        mock_servico.listar_atividades.return_value = [RESPOSTA_ATIVIDADE]
        resposta = client.get("/evento/1/atividade")
        assert resposta.status_code == 200
        assert isinstance(resposta.json(), list)
        assert len(resposta.json()) == 1

    def test_listar_atividades_evento_sem_atividades(self, client, mock_servico):
        mock_servico.listar_atividades.return_value = []
        resposta = client.get("/evento/1/atividade")
        assert resposta.status_code == 200
        assert resposta.json() == []

    def test_listar_atividades_multiplas(self, client, mock_servico):
        atividades = [
            {**ATIVIDADE_VALIDA, "atividade_id": i, "evento_id": 1, "nome": f"Atividade {i}"}
            for i in range(1, 4)
        ]
        mock_servico.listar_atividades.return_value = atividades
        resposta = client.get("/evento/1/atividade")
        assert len(resposta.json()) == 3

    @pytest.mark.parametrize("evento_id", [1, 5, 20])
    def test_listar_atividades_varios_eventos(self, client, mock_servico, evento_id):
        mock_servico.listar_atividades.return_value = []
        resposta = client.get(f"/evento/{evento_id}/atividade")
        assert resposta.status_code == 200
        mock_servico.listar_atividades.assert_called_with(evento_id)



class TestBuscarAtividade:

    def test_buscar_atividade_existente(self, client, mock_servico):
        mock_servico.buscar_atividade.return_value = RESPOSTA_ATIVIDADE
        resposta = client.get("/evento/atividade/1")
        assert resposta.status_code == 200
        assert resposta.json()["atividade_id"] == 1

    def test_buscar_atividade_nao_encontrada(self, client, mock_servico):
        mock_servico.buscar_atividade.side_effect = ValueError("Atividade não encontrada")
        resposta = client.get("/evento/atividade/999")
        assert resposta.status_code == 404
        assert "Atividade não encontrada" in resposta.json()["detail"]

    @pytest.mark.parametrize("atividade_id", [1, 3, 7, 50])
    def test_buscar_atividade_varios_ids(self, client, mock_servico, atividade_id):
        mock_servico.buscar_atividade.return_value = {
            **RESPOSTA_ATIVIDADE, "atividade_id": atividade_id
        }
        resposta = client.get(f"/evento/atividade/{atividade_id}")
        assert resposta.status_code == 200
        assert resposta.json()["atividade_id"] == atividade_id



class TestAtualizarAtividade:

    def test_atualizar_atividade_sucesso(self, client, mock_servico):
        atualizado = {**RESPOSTA_ATIVIDADE, "nome": "Nome Atualizado"}
        mock_servico.atualizar_atividade.return_value = atualizado
        resposta = client.put("/evento/atividade/1", json={**ATIVIDADE_VALIDA, "nome": "Nome Atualizado"})
        assert resposta.status_code == 200
        assert resposta.json()["nome"] == "Nome Atualizado"
        mock_servico.atualizar_atividade.assert_called_once()

    def test_atualizar_atividade_nao_encontrada(self, client, mock_servico):
        mock_servico.atualizar_atividade.side_effect = ValueError("Atividade não encontrada")
        resposta = client.put("/evento/atividade/999", json=ATIVIDADE_VALIDA)
        assert resposta.status_code == 400
        assert "Atividade não encontrada" in resposta.json()["detail"]

    def test_atualizar_atividade_horario_invalido(self, client, mock_servico):
        mock_servico.atualizar_atividade.side_effect = ValueError("Horário de término anterior ao início")
        resposta = client.put("/evento/atividade/1", json=ATIVIDADE_VALIDA)
        assert resposta.status_code == 400

    @pytest.mark.parametrize("campo_ausente", ["nome", "horario_inicio", "horario_termino"])
    def test_atualizar_campo_obrigatorio_ausente(self, client, mock_servico, campo_ausente):
        payload = {k: v for k, v in ATIVIDADE_VALIDA.items() if k != campo_ausente}
        resposta = client.put("/evento/atividade/1", json=payload)
        assert resposta.status_code == 422



class TestDeletarAtividade:

    def test_deletar_atividade_sucesso(self, client, mock_servico):
        mock_servico.deletar_atividade.return_value = None
        resposta = client.delete("/evento/atividade/1")
        assert resposta.status_code == 204
        mock_servico.deletar_atividade.assert_called_once_with(1)

    def test_deletar_atividade_nao_encontrada(self, client, mock_servico):
        mock_servico.deletar_atividade.side_effect = ValueError("Atividade não encontrada")
        resposta = client.delete("/evento/atividade/999")
        assert resposta.status_code == 404
        assert "Atividade não encontrada" in resposta.json()["detail"]

    @pytest.mark.parametrize("atividade_id", [1, 2, 5])
    def test_deletar_varios_ids(self, client, mock_servico, atividade_id):
        mock_servico.deletar_atividade.return_value = None
        resposta = client.delete(f"/evento/atividade/{atividade_id}")
        assert resposta.status_code == 204