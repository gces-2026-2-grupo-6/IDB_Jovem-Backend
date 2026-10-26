"""
US10 — Cadastro nacional de líderes.

Duas entregas no back-end:

* cargo único (RF58): dois líderes ativos não ocupam o mesmo par
  (cargo, região). Os casos básicos estão em test_especificacao_melhorias.py;
  aqui ficam a normalização do texto e os caminhos da edição.
* links fixados no painel: o de cadastro e o da planilha, só para a
  superadministradora, inclusive na leitura.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.lider.controller import router as lider_router, get_servico as get_servico_lider
from src.lider.schema import SolicitacaoLider
from src.lider.service import CargoOcupadoError, ServicoLider
from src.painel.controller import router as painel_router, get_servico as get_servico_painel
from src.painel.model import LinkPainel
from src.painel.repository import RepositorioLinkPainel
from src.painel.schema import SolicitacaoLinksPainel
from src.painel.service import ServicoLinkPainel
from src.security import obter_usuario_atual
from tests.unit.test_especificacao_melhorias import RepositorioLiderEmMemoria

SUPERADMIN = {"sub": "super-1", "realm_access": {"roles": ["superadmin"]}}
ADMIN = {"sub": "admin-1", "realm_access": {"roles": ["admin", "admin-eventos"]}}

CADASTRO = "https://forms.gle/cadastro-lideres"
PLANILHA = "https://docs.google.com/spreadsheets/d/planilha-lideres"


@pytest.fixture
def servico_lider() -> ServicoLider:
    return ServicoLider(RepositorioLiderEmMemoria())


# ---------------------------------------------------------------- cargo único


class TestCargoUnico:

    @pytest.mark.parametrize(
        "cargo,regiao",
        [
            ("vice-diretor nacional", None),
            ("VICE DIRETOR NACIONAL", None),
            ("  Vice-Diretor   Nacional ", ""),
        ],
    )
    def test_variacao_de_escrita_nao_burla_a_regra(self, servico_lider, cargo, regiao):
        servico_lider.criar_lider(SolicitacaoLider(nome="Ana", cargo="Vice-Diretor Nacional"))

        with pytest.raises(CargoOcupadoError):
            servico_lider.criar_lider(SolicitacaoLider(nome="Bruno", cargo=cargo, regiao=regiao))

    def test_regiao_com_acento_e_hifen_conta_como_a_mesma(self, servico_lider):
        servico_lider.criar_lider(
            SolicitacaoLider(nome="Ana", cargo="Diretor Regional", regiao="Centro-Oeste")
        )

        with pytest.raises(CargoOcupadoError):
            servico_lider.criar_lider(
                SolicitacaoLider(nome="Bruno", cargo="Diretor Regional", regiao="centro oeste")
            )

    def test_mensagem_explica_quem_ocupa_e_como_liberar(self, servico_lider):
        servico_lider.criar_lider(
            SolicitacaoLider(nome="Ana Souza", cargo="Diretor Regional", regiao="Sul")
        )

        with pytest.raises(CargoOcupadoError) as erro:
            servico_lider.criar_lider(
                SolicitacaoLider(nome="Bruno", cargo="Diretor Regional", regiao="Sul")
            )

        assert "Ana Souza" in str(erro.value)
        assert "Sul" in str(erro.value)
        assert "diretor anterior" in str(erro.value)

    def test_cadastrar_diretor_anterior_no_cargo_ocupado_e_permitido(self, servico_lider):
        servico_lider.criar_lider(SolicitacaoLider(nome="Ana", cargo="Diretor Nacional"))
        servico_lider.criar_lider(
            SolicitacaoLider(nome="Carlos", cargo="Diretor Nacional", is_antigo=True)
        )

        assert len(servico_lider.listar_diretores_anteriores()) == 1

    def test_editar_o_proprio_lider_sem_mudar_cargo_e_permitido(self, servico_lider):
        ana = servico_lider.criar_lider(SolicitacaoLider(nome="Ana", cargo="Diretor Nacional"))

        atualizado = servico_lider.atualizar_lider(
            ana.lider_id,
            SolicitacaoLider(nome="Ana Souza", cargo="Diretor Nacional", ordem=2),
        )

        assert atualizado.nome == "Ana Souza"

    def test_troca_de_mandato_pela_edicao(self, servico_lider):
        """Fluxo do CA7: marca a anterior como antiga e só então cadastra o novo."""
        ana = servico_lider.criar_lider(SolicitacaoLider(nome="Ana", cargo="Diretor Nacional"))

        servico_lider.atualizar_lider(
            ana.lider_id,
            SolicitacaoLider(nome="Ana", cargo="Diretor Nacional", is_antigo=True),
        )
        servico_lider.criar_lider(SolicitacaoLider(nome="Bruno", cargo="Diretor Nacional"))

        assert [l.nome for l in servico_lider.listar_lideres_atuais()] == ["Bruno"]

    def test_reativar_diretor_anterior_em_cargo_ocupado_e_recusado(self, servico_lider):
        servico_lider.criar_lider(SolicitacaoLider(nome="Ana", cargo="Diretor Nacional"))
        carlos = servico_lider.criar_lider(
            SolicitacaoLider(nome="Carlos", cargo="Diretor Nacional", is_antigo=True)
        )

        with pytest.raises(CargoOcupadoError):
            servico_lider.atualizar_lider(
                carlos.lider_id,
                SolicitacaoLider(nome="Carlos", cargo="Diretor Nacional", is_antigo=False),
            )

        assert carlos.is_antigo is True, "A recusa não pode deixar o registro alterado."

    def test_mudar_so_a_regiao_para_uma_ocupada_e_recusado(self, servico_lider):
        servico_lider.criar_lider(
            SolicitacaoLider(nome="Ana", cargo="Diretor Regional", regiao="Sul")
        )
        bruno = servico_lider.criar_lider(
            SolicitacaoLider(nome="Bruno", cargo="Diretor Regional", regiao="Norte")
        )

        with pytest.raises(CargoOcupadoError):
            servico_lider.atualizar_lider(
                bruno.lider_id,
                SolicitacaoLider(nome="Bruno", cargo="Diretor Regional", regiao="Sul"),
            )


def _client_lider(servico, usuario=SUPERADMIN):
    app = FastAPI()
    app.include_router(lider_router)
    app.dependency_overrides[get_servico_lider] = lambda: servico
    app.dependency_overrides[obter_usuario_atual] = lambda: usuario
    return TestClient(app)


class TestCargoUnicoNaApi:

    def test_post_em_cargo_ocupado_responde_409(self):
        servico = MagicMock()
        servico.criar_lider.side_effect = CargoOcupadoError("O cargo já está ocupado.")

        resposta = _client_lider(servico).post(
            "/lider/", json={"nome": "Bruno", "cargo": "Diretor Nacional"}
        )

        assert resposta.status_code == 409
        assert resposta.json() == {"detail": "O cargo já está ocupado."}

    def test_put_em_cargo_ocupado_responde_409_e_nao_404(self):
        servico = MagicMock()
        servico.atualizar_lider.side_effect = CargoOcupadoError("O cargo já está ocupado.")

        resposta = _client_lider(servico).put(
            "/lider/1", json={"nome": "Bruno", "cargo": "Diretor Nacional"}
        )

        assert resposta.status_code == 409

    def test_put_de_lider_inexistente_continua_404(self):
        servico = MagicMock()
        servico.atualizar_lider.side_effect = ValueError("Líder não encontrado.")

        resposta = _client_lider(servico).put(
            "/lider/99", json={"nome": "Bruno", "cargo": "Diretor Nacional"}
        )

        assert resposta.status_code == 404


# ------------------------------------------------------- links fixados no painel


@pytest.fixture
def banco():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    LinkPainel.__table__.create(engine)
    sessao = sessionmaker(bind=engine)()
    yield sessao
    sessao.close()


@pytest.fixture
def servico_painel(banco) -> ServicoLinkPainel:
    return ServicoLinkPainel(RepositorioLinkPainel(banco))


class TestValidacaoDosLinks:

    def test_link_precisa_ser_http(self):
        with pytest.raises(ValidationError):
            SolicitacaoLinksPainel(link_cadastro_lideres="forms.gle/abc")

    def test_link_nao_texto_e_recusado(self):
        with pytest.raises(ValidationError):
            SolicitacaoLinksPainel(link_planilha_lideres=123)

    def test_espacos_sao_removidos(self):
        dados = SolicitacaoLinksPainel(link_cadastro_lideres=f"  {CADASTRO}  ")
        assert dados.link_cadastro_lideres == CADASTRO

    @pytest.mark.parametrize("vazio", ["", "   ", None])
    def test_vazio_vira_nulo(self, vazio):
        dados = SolicitacaoLinksPainel(link_cadastro_lideres=vazio)
        assert dados.link_cadastro_lideres is None


class TestServicoDosLinks:

    def test_sem_configuracao_os_dois_vem_nulos(self, servico_painel):
        links = servico_painel.obter_links()
        assert links.link_cadastro_lideres is None
        assert links.link_planilha_lideres is None

    def test_grava_e_le_os_dois_links(self, servico_painel):
        servico_painel.atualizar_links(
            SolicitacaoLinksPainel(
                link_cadastro_lideres=CADASTRO, link_planilha_lideres=PLANILHA
            )
        )

        links = servico_painel.obter_links()
        assert links.link_cadastro_lideres == CADASTRO
        assert links.link_planilha_lideres == PLANILHA

    def test_atualizacao_parcial_nao_apaga_o_outro_link(self, servico_painel):
        """CA4: trocar um dos links não pode zerar o outro."""
        servico_painel.atualizar_links(
            SolicitacaoLinksPainel(
                link_cadastro_lideres=CADASTRO, link_planilha_lideres=PLANILHA
            )
        )

        novo = "https://forms.gle/novo-cadastro"
        links = servico_painel.atualizar_links(
            SolicitacaoLinksPainel(link_cadastro_lideres=novo)
        )

        assert links.link_cadastro_lideres == novo
        assert links.link_planilha_lideres == PLANILHA

    def test_enviar_vazio_remove_o_link(self, servico_painel, banco):
        servico_painel.atualizar_links(SolicitacaoLinksPainel(link_planilha_lideres=PLANILHA))

        links = servico_painel.atualizar_links(SolicitacaoLinksPainel(link_planilha_lideres=""))

        assert links.link_planilha_lideres is None
        assert banco.query(LinkPainel).count() == 0

    def test_remover_link_inexistente_nao_falha(self, servico_painel):
        links = servico_painel.atualizar_links(SolicitacaoLinksPainel(link_planilha_lideres=None))
        assert links.link_planilha_lideres is None


def _client_painel(servico, usuario):
    app = FastAPI()
    app.include_router(painel_router)
    app.dependency_overrides[get_servico_painel] = lambda: servico
    app.dependency_overrides[obter_usuario_atual] = lambda: usuario
    return TestClient(app)


class TestRotasDosLinks:

    def test_superadmin_le_os_links(self, servico_painel):
        servico_painel.atualizar_links(SolicitacaoLinksPainel(link_cadastro_lideres=CADASTRO))

        resposta = _client_painel(servico_painel, SUPERADMIN).get("/painel/links")

        assert resposta.status_code == 200
        assert resposta.json() == {
            "link_cadastro_lideres": CADASTRO,
            "link_planilha_lideres": None,
        }

    def test_superadmin_atualiza_os_links(self, servico_painel):
        resposta = _client_painel(servico_painel, SUPERADMIN).put(
            "/painel/links", json={"link_planilha_lideres": PLANILHA}
        )

        assert resposta.status_code == 200
        assert resposta.json()["link_planilha_lideres"] == PLANILHA

    def test_link_invalido_responde_422(self, servico_painel):
        resposta = _client_painel(servico_painel, SUPERADMIN).put(
            "/painel/links", json={"link_planilha_lideres": "planilha"}
        )

        assert resposta.status_code == 422

    @pytest.mark.parametrize("metodo", ["get", "put"])
    def test_admin_de_setor_nao_ve_nem_altera(self, servico_painel, metodo):
        """CA3: administrador de setor não enxerga os links."""
        cliente = _client_painel(servico_painel, ADMIN)
        resposta = getattr(cliente, metodo)("/painel/links", **({"json": {}} if metodo == "put" else {}))

        assert resposta.status_code == 403


def test_injecao_do_servico_de_links_usa_o_banco_da_requisicao():
    banco = MagicMock()
    servico = get_servico_painel(banco)
    assert isinstance(servico, ServicoLinkPainel)
    assert servico.repositorio.db is banco
