import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.lider.controller import router as lider_router, get_servico
from src.security import obter_usuario_atual
from tests.unit.lider_dados_teste import (
    lider_atual_brasileiro,
    diretor_anterior_brasileiro,
    diretor_anterior_estrangeiro,
)


USUARIO_SUPERADMIN = {"sub": "super-1", "realm_access": {"roles": ["superadmin"]}}
USUARIO_ADMIN = {"sub": "admin-1", "realm_access": {"roles": ["admin"]}}

PERFIL_COMPLETO = {
    "nome": "Ana Souza",
    "cargo": "Coordenadora Geral",
    "imagem_url": "https://exemplo.org/fotos/ana-souza.jpg",
    "is_antigo": False,
    "ordem": 1,
    "regiao": "Sudeste",
    "mini_biografia": "Atua na coordenação geral do ministério jovem desde 2022.",
    "redes_sociais": {
        "instagram": "https://instagram.com/ana.souza.exemplo",
        "linkedin": "https://linkedin.com/in/ana-souza-exemplo",
    },
}

# Formato que o painel do front-end envia hoje (liderService.toLiderPayload).
PAYLOAD_PAINEL_ATUAL = {
    "nome": "Ana Souza",
    "cargo": "Coordenadora Geral",
    "imagem_url": "",
    "is_antigo": False,
    "ordem": 0,
    "regiao": "",
    "bio": "",
    "redes_sociais": "",
    "gestao": "",
}

ROTAS_DE_ESCRITA = [
    pytest.param("post", "/lider/", PERFIL_COMPLETO, id="POST /lider"),
    pytest.param("put", "/lider/1", PERFIL_COMPLETO, id="PUT /lider/{id}"),
    pytest.param("delete", "/lider/1", None, id="DELETE /lider/{id}"),
]


def _montar_client(servico_mock, usuario=None):
    app = FastAPI()
    app.include_router(lider_router)
    app.dependency_overrides[get_servico] = lambda: servico_mock
    if usuario is not None:
        app.dependency_overrides[obter_usuario_atual] = lambda: usuario
    return TestClient(app)


def _chamar(client, metodo, rota, corpo):
    if corpo is None:
        return getattr(client, metodo)(rota)
    return getattr(client, metodo)(rota, json=corpo)


@pytest.fixture
def servico_mock():
    return MagicMock()


@pytest.fixture
def client_superadmin(servico_mock):
    with _montar_client(servico_mock, USUARIO_SUPERADMIN) as client:
        yield client, servico_mock


@pytest.fixture
def client_publico(servico_mock):
    with _montar_client(servico_mock) as client:
        yield client, servico_mock


class TestLeituraPublica:
    def test_listar_expoe_campos_de_perfil(self, client_publico):
        client, servico = client_publico
        servico.listar_lideres.return_value = [lider_atual_brasileiro()]

        response = client.get("/lider/")

        assert response.status_code == 200
        lider = response.json()[0]
        assert lider["regiao"] == "Sudeste"
        assert lider["mini_biografia"]
        assert lider["redes_sociais"] == {
            "instagram": "https://instagram.com/ana.souza.exemplo",
            "linkedin": "https://linkedin.com/in/ana-souza-exemplo",
        }

    def test_listar_lideres_atuais(self, client_publico):
        client, servico = client_publico
        servico.listar_lideres_atuais.return_value = [lider_atual_brasileiro()]

        response = client.get("/lider/atuais")

        assert response.status_code == 200
        assert [l["is_antigo"] for l in response.json()] == [False]
        servico.listar_lideres_atuais.assert_called_once()
        servico.buscar_lider.assert_not_called()

    def test_listar_diretores_anteriores(self, client_publico):
        client, servico = client_publico
        servico.listar_diretores_anteriores.return_value = [
            diretor_anterior_brasileiro(),
            diretor_anterior_estrangeiro(),
        ]

        response = client.get("/lider/diretores-anteriores")

        assert response.status_code == 200
        assert [l["lider_id"] for l in response.json()] == [2, 3]
        assert all(l["is_antigo"] for l in response.json())
        servico.buscar_lider.assert_not_called()

    def test_buscar_por_id(self, client_publico):
        client, servico = client_publico
        servico.buscar_lider.return_value = diretor_anterior_estrangeiro()

        response = client.get("/lider/3")

        assert response.status_code == 200
        assert response.json()["regiao"] == "América Latina - Argentina"
        servico.buscar_lider.assert_called_once_with(3)

    def test_buscar_por_id_inexistente_retorna_404(self, client_publico):
        client, servico = client_publico
        servico.buscar_lider.side_effect = ValueError("Líder não encontrado.")

        assert client.get("/lider/999").status_code == 404


class TestEscritaComSuperadmin:
    def test_criar_com_perfil_completo(self, client_superadmin):
        client, servico = client_superadmin
        servico.criar_lider.return_value = lider_atual_brasileiro()

        response = client.post("/lider/", json=PERFIL_COMPLETO)

        assert response.status_code == 201
        assert response.json()["redes_sociais"]["instagram"].startswith("https://")
        solicitacao = servico.criar_lider.call_args.args[0]
        assert solicitacao.redes_sociais == PERFIL_COMPLETO["redes_sociais"]

    def test_criar_aceita_payload_do_painel_atual(self, client_superadmin):
        client, servico = client_superadmin
        servico.criar_lider.return_value = lider_atual_brasileiro(
            regiao=None, mini_biografia=None, redes_sociais=None
        )

        response = client.post("/lider/", json=PAYLOAD_PAINEL_ATUAL)

        assert response.status_code == 201
        solicitacao = servico.criar_lider.call_args.args[0]
        assert solicitacao.regiao is None
        assert solicitacao.redes_sociais is None

    def test_criar_com_redes_sociais_em_texto_retorna_422(self, client_superadmin):
        client, servico = client_superadmin

        response = client.post(
            "/lider/", json={**PERFIL_COMPLETO, "redes_sociais": "@ana, youtube.com/ana"}
        )

        assert response.status_code == 422
        servico.criar_lider.assert_not_called()

    def test_criar_sem_campos_obrigatorios_retorna_422(self, client_superadmin):
        client, servico = client_superadmin

        assert client.post("/lider/", json={"regiao": "Sul"}).status_code == 422
        servico.criar_lider.assert_not_called()

    def test_atualizar(self, client_superadmin):
        client, servico = client_superadmin
        servico.atualizar_lider.return_value = diretor_anterior_brasileiro()

        response = client.put("/lider/2", json={**PERFIL_COMPLETO, "is_antigo": True})

        assert response.status_code == 200
        assert response.json()["is_antigo"] is True
        servico.atualizar_lider.assert_called_once()

    def test_atualizar_inexistente_retorna_404(self, client_superadmin):
        client, servico = client_superadmin
        servico.atualizar_lider.side_effect = ValueError("Líder não encontrado.")

        assert client.put("/lider/999", json=PERFIL_COMPLETO).status_code == 404

    def test_deletar(self, client_superadmin):
        client, servico = client_superadmin

        response = client.delete("/lider/1")

        assert response.status_code == 204
        servico.deletar_lider.assert_called_once_with(1)

    def test_deletar_inexistente_retorna_404(self, client_superadmin):
        client, servico = client_superadmin
        servico.deletar_lider.side_effect = ValueError("Líder não encontrado.")

        assert client.delete("/lider/999").status_code == 404


class TestEscritaRestritaASuperadmin:
    @pytest.mark.parametrize("metodo, rota, corpo", ROTAS_DE_ESCRITA)
    def test_admin_recebe_403(self, servico_mock, metodo, rota, corpo):
        with _montar_client(servico_mock, USUARIO_ADMIN) as client:
            response = _chamar(client, metodo, rota, corpo)

        assert response.status_code == 403
        assert servico_mock.method_calls == []

    @pytest.mark.parametrize("metodo, rota, corpo", ROTAS_DE_ESCRITA)
    def test_papel_de_setor_nao_concede_acesso(self, servico_mock, metodo, rota, corpo):
        usuario = {"sub": "setor-1", "realm_access": {"roles": ["admin", "admin-eventos"]}}
        with _montar_client(servico_mock, usuario) as client:
            response = _chamar(client, metodo, rota, corpo)

        assert response.status_code == 403
        assert servico_mock.method_calls == []

    @pytest.mark.parametrize("metodo, rota, corpo", ROTAS_DE_ESCRITA)
    def test_sem_token_e_recusado(self, client_publico, metodo, rota, corpo):
        client, servico = client_publico

        response = _chamar(client, metodo, rota, corpo)

        assert response.status_code in (401, 403)
        assert servico.method_calls == []


class TestErrosPadronizados:
    @pytest.mark.parametrize(
        "metodo, rota, corpo, servico_metodo",
        [
            pytest.param("get", "/lider/999", None, "buscar_lider", id="GET"),
            pytest.param("put", "/lider/999", PERFIL_COMPLETO, "atualizar_lider", id="PUT"),
            pytest.param("delete", "/lider/999", None, "deletar_lider", id="DELETE"),
        ],
    )
    def test_404_tem_mensagem_unica(self, client_superadmin, metodo, rota, corpo, servico_metodo):
        client, servico = client_superadmin
        getattr(servico, servico_metodo).side_effect = ValueError("Líder não encontrado.")

        response = _chamar(client, metodo, rota, corpo)

        assert response.status_code == 404
        assert response.json() == {"detail": "Líder não encontrado."}

    def test_403_informa_o_papel_exigido(self, servico_mock):
        with _montar_client(servico_mock, USUARIO_ADMIN) as client:
            response = client.post("/lider/", json=PERFIL_COMPLETO)

        assert response.status_code == 403
        assert "superadmin" in response.json()["detail"]

    def test_422_de_redes_sociais_explica_o_formato(self, client_superadmin):
        client, _ = client_superadmin

        response = client.post("/lider/", json={**PERFIL_COMPLETO, "redes_sociais": "@ana"})

        assert response.status_code == 422
        erro = response.json()["detail"][0]
        assert erro["loc"] == ["body", "redes_sociais"]
        assert "objeto JSON" in erro["msg"]

    def test_openapi_declara_os_erros_de_cada_rota(self, client_publico):
        client, _ = client_publico
        caminhos = client.app.openapi()["paths"]

        def codigos(caminho, metodo):
            return set(caminhos[caminho][metodo]["responses"])

        assert {"201", "401", "403", "422"} <= codigos("/lider/", "post")
        assert {"200", "404", "422"} <= codigos("/lider/{lider_id}", "get")
        assert {"200", "401", "403", "404", "422"} <= codigos("/lider/{lider_id}", "put")
        assert {"204", "401", "403", "404"} <= codigos("/lider/{lider_id}", "delete")
        assert set(caminhos) >= {"/lider/", "/lider/atuais", "/lider/diretores-anteriores"}

    def test_openapi_documenta_o_formato_do_erro(self, client_publico):
        client, _ = client_publico
        esquema = client.app.openapi()

        resposta_404 = esquema["paths"]["/lider/{lider_id}"]["get"]["responses"]["404"]
        referencia = resposta_404["content"]["application/json"]["schema"]["$ref"]
        assert referencia.endswith("/ErroResposta")
        assert esquema["components"]["schemas"]["ErroResposta"]["required"] == ["detail"]
