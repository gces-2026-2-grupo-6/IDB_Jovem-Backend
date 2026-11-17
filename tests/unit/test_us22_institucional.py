"""
US22 — Missão, visão e valores.

* GET /institucional é público e, enquanto nada foi salvo, devolve missão e
  visão nulas e lista de valores vazia — o front não inventa texto;
* PUT /institucional é só da superadministradora, substitui o conteúdo por
  inteiro, apara os textos e devolve o que ficou salvo.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.institucional.controller import get_servico, router
from src.institucional.model import Institucional
from src.institucional.repository import RepositorioInstitucional
from src.institucional.schema import SolicitacaoInstitucional
from src.institucional.service import ServicoInstitucional
from src.security import obter_usuario_atual

SUPERADMIN = {"sub": "super-1", "realm_access": {"roles": ["superadmin"]}}
ADMIN = {"sub": "admin-1", "realm_access": {"roles": ["admin"]}}


@pytest.fixture
def banco():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Institucional.__table__.create(engine)
    sessao = sessionmaker(bind=engine)()
    yield sessao
    sessao.close()


@pytest.fixture
def servico(banco) -> ServicoInstitucional:
    return ServicoInstitucional(RepositorioInstitucional(banco))


def _client(servico_institucional, usuario=None):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_servico] = lambda: servico_institucional
    if usuario is not None:
        app.dependency_overrides[obter_usuario_atual] = lambda: usuario
    return TestClient(app)


# ------------------------------------------------------------------- validação


class TestValidacao:

    def test_textos_sao_aparados(self):
        dados = SolicitacaoInstitucional(missao="  Nossa missão  ", visao="  Visão  ")

        assert dados.missao == "Nossa missão"
        assert dados.visao == "Visão"

    def test_texto_em_branco_vira_nulo(self):
        dados = SolicitacaoInstitucional(
            missao="   ", visao="", valores=["Fé"]
        )
        nulos = SolicitacaoInstitucional(missao=None, visao=None, valores=["Fé"])

        assert dados.missao is None
        assert dados.visao is None
        assert (nulos.missao, nulos.visao) == (None, None)

    def test_valores_em_branco_sao_descartados(self):
        dados = SolicitacaoInstitucional(valores=["  Fé  ", "", "   ", "Serviço"])

        assert dados.valores == ["Fé", "Serviço"]

    def test_valores_nulos_viram_lista_vazia(self):
        dados = SolicitacaoInstitucional(missao="Inspirar", valores=None)

        assert dados.valores == []

    def test_missao_ou_visao_precisa_ser_texto(self):
        with pytest.raises(ValidationError):
            SolicitacaoInstitucional(missao=123)

    def test_valores_precisa_ser_lista(self):
        with pytest.raises(ValidationError):
            SolicitacaoInstitucional(valores="Fé")

    def test_cada_valor_precisa_ser_texto(self):
        with pytest.raises(ValidationError):
            SolicitacaoInstitucional(valores=["Fé", 1])

    def test_conteudo_todo_vazio_e_recusado(self):
        with pytest.raises(ValidationError, match="Preencha ao menos"):
            SolicitacaoInstitucional()

        with pytest.raises(ValidationError, match="Preencha ao menos"):
            SolicitacaoInstitucional(missao="  ", visao="", valores=["", "  "])


# --------------------------------------------------------------------- serviço


class TestServico:

    def test_sem_conteudo_salvo_devolve_nulos_e_lista_vazia(self, servico):
        resposta = servico.obter_conteudo()

        assert resposta.missao is None
        assert resposta.visao is None
        assert resposta.valores == []

    def test_salva_e_le_de_volta(self, servico):
        salvo = servico.atualizar_conteudo(
            SolicitacaoInstitucional(
                missao="Inspirar",
                visao="Ser referência",
                valores=["Fé", "Serviço"],
            )
        )

        assert salvo.missao == "Inspirar"
        assert salvo.visao == "Ser referência"
        assert salvo.valores == ["Fé", "Serviço"]
        assert servico.obter_conteudo().model_dump() == salvo.model_dump()

    def test_segunda_gravacao_atualiza_o_mesmo_registro(self, servico, banco):
        servico.atualizar_conteudo(SolicitacaoInstitucional(missao="Primeira"))
        servico.atualizar_conteudo(SolicitacaoInstitucional(visao="Segunda"))

        assert banco.query(Institucional).count() == 1
        conteudo = servico.obter_conteudo()
        assert conteudo.missao is None
        assert conteudo.visao == "Segunda"
        assert conteudo.valores == []


# ---------------------------------------------------------------------- rotas


class TestRotas:

    def test_get_publico_sem_conteudo(self, servico):
        resposta = _client(servico).get("/institucional")

        assert resposta.status_code == 200
        assert resposta.json() == {"missao": None, "visao": None, "valores": []}

    def test_superadmin_salva_e_get_reflete(self, servico):
        cliente = _client(servico, SUPERADMIN)
        corpo = {"missao": "  Inspirar  ", "visao": "", "valores": [" Fé ", ""]}

        salvo = cliente.put("/institucional", json=corpo)

        assert salvo.status_code == 200
        assert salvo.json() == {
            "missao": "Inspirar",
            "visao": None,
            "valores": ["Fé"],
        }
        assert cliente.get("/institucional").json() == salvo.json()

    def test_corpo_todo_vazio_e_recusado(self, servico):
        resposta = _client(servico, SUPERADMIN).put("/institucional", json={})

        assert resposta.status_code == 422

    def test_admin_de_setor_nao_edita(self, servico):
        resposta = _client(servico, ADMIN).put(
            "/institucional", json={"missao": "Tentativa"}
        )

        assert resposta.status_code == 403

    def test_get_continua_publico_para_quem_tem_outro_papel(self, servico):
        cliente = _client(servico, ADMIN)

        assert cliente.get("/institucional").status_code == 200


def test_injecao_do_servico_usa_o_banco_da_requisicao():
    db = MagicMock()

    assert get_servico(db).repositorio.db is db
