"""Rota de inscritos no formulario de participantes (US09).

Os dois fluxos de inscricao do evento sao independentes: cada um tem seu
link e sua listagem, e so quem administra o setor de inscricoes enxerga os
dados pessoais de quem se inscreveu.
"""
import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.formulario.controller import router, get_servico
from src.formulario.schema import RespostaInscricaoParticipante
from src.security import obter_usuario_atual

ROTA = "/formulario/eventos/1/participantes"

USUARIO_INSCRICOES = {"realm_access": {"roles": ["admin", "admin-inscricoes"]}}
USUARIO_EVENTOS = {"realm_access": {"roles": ["admin", "admin-eventos"]}}

INSCRITO = RespostaInscricaoParticipante(
    evento_id=1,
    participante_id=7,
    nome="Ana Souza",
    email="ana@exemplo.org",
    resposta_id="resp-1",
    link_resposta="https://docs.google.com/forms/d/part123/edit#response=resp-1",
)


@pytest.fixture
def mock_servico():
    return MagicMock()


def _app(mock_servico, usuario=None):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_servico] = lambda: mock_servico
    if usuario is not None:
        app.dependency_overrides[obter_usuario_atual] = lambda: usuario
    return app


@pytest.fixture
def client(mock_servico):
    with TestClient(_app(mock_servico, USUARIO_INSCRICOES)) as c:
        yield c, mock_servico


class TestAutorizacao:
    def test_sem_token_e_negado(self, mock_servico):
        with TestClient(_app(mock_servico)) as c:
            resposta = c.get(ROTA)

        assert resposta.status_code in (401, 403)
        mock_servico.listar_participantes.assert_not_called()

    def test_admin_de_outro_setor_e_negado(self, mock_servico):
        with TestClient(_app(mock_servico, USUARIO_EVENTOS)) as c:
            resposta = c.get(ROTA)

        assert resposta.status_code == 403
        mock_servico.listar_participantes.assert_not_called()

    def test_setor_de_inscricoes_tem_acesso(self, client):
        c, servico = client
        servico.listar_participantes.return_value = []

        assert c.get(ROTA).status_code == 200

    def test_superadmin_tem_acesso(self, mock_servico):
        mock_servico.listar_participantes.return_value = []
        with TestClient(_app(mock_servico, {"realm_access": {"roles": ["superadmin"]}})) as c:
            assert c.get(ROTA).status_code == 200


class TestListagem:
    def test_devolve_os_inscritos_do_evento(self, client):
        c, servico = client
        servico.listar_participantes.return_value = [INSCRITO]

        resposta = c.get(ROTA)

        assert resposta.status_code == 200
        corpo = resposta.json()[0]
        assert corpo["participante_id"] == 7
        assert corpo["nome"] == "Ana Souza"
        assert corpo["email"] == "ana@exemplo.org"
        assert corpo["link_resposta"].endswith("#response=resp-1")
        servico.listar_participantes.assert_called_once()

    def test_resposta_nao_traz_status(self, client):
        """Criterio 3: pendente/aprovado/reprovado e so do voluntariado."""
        c, servico = client
        servico.listar_participantes.return_value = [INSCRITO]

        assert "status" not in resposta_unica(c)

    def test_lista_vazia_quando_ninguem_se_inscreveu(self, client):
        c, servico = client
        servico.listar_participantes.return_value = []

        assert c.get(ROTA).json() == []

    def test_evento_sem_formulario_de_participantes_responde_404(self, client):
        c, servico = client
        servico.listar_participantes.side_effect = ValueError(
            "Evento sem formulario de participantes configurado"
        )

        resposta = c.get(ROTA)

        assert resposta.status_code == 404
        assert "participantes" in resposta.json()["detail"]

    def test_falha_do_google_responde_502(self, client):
        c, servico = client
        servico.listar_participantes.side_effect = RuntimeError(
            "Falha ao buscar respostas no Google Forms"
        )

        assert c.get(ROTA).status_code == 502


class TestFluxosSeparados:
    def test_listar_participantes_nao_toca_no_fluxo_de_voluntarios(self, client):
        c, servico = client
        servico.listar_participantes.return_value = []

        c.get(ROTA)

        servico.listar_inscricoes.assert_not_called()

    def test_listar_voluntarios_nao_toca_no_fluxo_de_participantes(self, client):
        c, servico = client
        servico.listar_inscricoes.return_value = []

        c.get("/formulario/eventos/1/inscricoes")

        servico.listar_participantes.assert_not_called()


def resposta_unica(client):
    return client.get(ROTA).json()[0]
