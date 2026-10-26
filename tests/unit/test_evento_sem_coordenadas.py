"""
Evento sem latitude e longitude na listagem publica.

As colunas local_latitude e local_longitude aceitam nulo no banco, mas o schema
de resposta as declarava como obrigatorias. Bastava um evento sem coordenadas —
cadastrado por outro caminho, vindo de dado antigo ou importado da agenda — para
"GET /evento/" responder 500 e derrubar a listagem inteira, inclusive a publica:
o erro e de serializacao da resposta, entao nenhum evento chega ao visitante.

Isto tambem e pre-requisito da US19: evento online nao tem endereco, logo nao
tem coordenadas. Enquanto a resposta exigir os dois numeros, o primeiro evento
online publicado repete a mesma queda.

Os testes cobrem a serializacao (RespostaEvento) e a rota, com o servico
simulado, porque o defeito esta no contrato da resposta e nao no banco.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.evento.controller import get_servico
from src.evento.controller import router as evento_router
from src.evento.schema import RespostaEvento
from src.security import obter_usuario_atual

USUARIO_ADMIN = {"sub": "user-1", "realm_access": {"roles": ["admin", "superadmin"]}}

EVENTO_PRESENCIAL = {
    "evento_id": 1,
    "nome": "Congresso Nacional",
    "tipo_evento": "Conferência",
    "descricao": "Evento com endereço",
    "local_latitude": -15.7801,
    "local_longitude": -47.9292,
    "nome_local": "Templo Sede",
    "data_inicio": "2026-11-10T19:00:00",
    "data_fim": "2026-11-12T21:00:00",
}

EVENTO_SEM_COORDENADAS = {
    "evento_id": 2,
    "nome": "Live de oração",
    "tipo_evento": "Outros",
    "descricao": "Evento sem endereço",
    "local_latitude": None,
    "local_longitude": None,
    "nome_local": None,
    "data_inicio": "2026-11-20T20:00:00",
    "data_fim": "2026-11-20T22:00:00",
}


@pytest.fixture
def servico():
    return MagicMock()


@pytest.fixture
def client(servico):
    app = FastAPI()
    app.include_router(evento_router)
    app.dependency_overrides[get_servico] = lambda: servico
    app.dependency_overrides[obter_usuario_atual] = lambda: USUARIO_ADMIN
    with TestClient(app) as cliente:
        yield cliente
    app.dependency_overrides.clear()


class TestSerializacao:
    """O contrato da resposta e onde o defeito morava."""

    def test_evento_sem_coordenadas_e_serializavel(self):
        resposta = RespostaEvento(**EVENTO_SEM_COORDENADAS)
        assert resposta.local_latitude is None
        assert resposta.local_longitude is None

    def test_evento_com_coordenadas_mantem_os_numeros(self):
        resposta = RespostaEvento(**EVENTO_PRESENCIAL)
        assert resposta.local_latitude == pytest.approx(-15.7801)
        assert resposta.local_longitude == pytest.approx(-47.9292)

    def test_coordenada_so_de_um_lado_nao_derruba(self):
        """Dado antigo as vezes tem latitude e nao tem longitude."""
        meia = {**EVENTO_SEM_COORDENADAS, "local_latitude": -15.7801}
        resposta = RespostaEvento(**meia)
        assert resposta.local_latitude == pytest.approx(-15.7801)
        assert resposta.local_longitude is None


class TestListagemPublica:

    def test_listagem_com_evento_sem_coordenadas_responde_200(self, client, servico):
        servico.listar_evento.return_value = [EVENTO_SEM_COORDENADAS]
        resposta = client.get("/evento/")
        assert resposta.status_code == 200
        assert [e["nome"] for e in resposta.json()] == ["Live de oração"]

    def test_um_evento_sem_coordenadas_nao_derruba_os_demais(self, client, servico):
        """
        Era este o efeito real: o erro de serializacao vale para a resposta
        inteira, entao um unico registro incompleto escondia todos os outros.
        """
        servico.listar_evento.return_value = [EVENTO_PRESENCIAL, EVENTO_SEM_COORDENADAS]
        resposta = client.get("/evento/")
        assert resposta.status_code == 200
        assert len(resposta.json()) == 2

    def test_busca_por_id_do_evento_sem_coordenadas(self, client, servico):
        servico.buscar_evento.return_value = EVENTO_SEM_COORDENADAS
        resposta = client.get("/evento/2")
        assert resposta.status_code == 200
        assert resposta.json()["local_latitude"] is None


class TestCadastro:
    """
    Ler evento sem coordenadas e uma coisa; cadastrar sem elas e outra.
    Enquanto a US19 nao trouxer a modalidade, o cadastro continua exigindo
    endereco — e este teste e o que vai acusar quando essa regra mudar.
    """

    def test_criar_evento_sem_coordenadas_e_recusado(self, client, servico):
        sem_coordenadas = {
            "nome": "Live de oração",
            "tipo_evento": "Outros",
            "data_inicio": "2026-11-20T20:00:00",
            "data_fim": "2026-11-20T22:00:00",
        }
        resposta = client.post("/evento/", json=sem_coordenadas)
        assert resposta.status_code == 422
        servico.criar_evento.assert_not_called()
