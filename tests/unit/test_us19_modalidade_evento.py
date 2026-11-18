"""
US19 (RF56) — Eventos online e presenciais separados.

O back-end da US19 entrou sem suite propria: a regra estava coberta so pelos
testes de endpoint (que exigem o container) e pelos `xfail` da EX-02. Na
suite unitaria, o ramo online de `criar_evento` e de `atualizar_evento`
nunca executava. Este modulo cobre o que o servidor ja entrega:

* CA1 — a modalidade e marcada no proprio cadastro; online desobriga o
  endereco, presencial continua exigindo latitude e longitude;
* CA3 — evento online sem endereco e sem coordenadas e aceito e a listagem
  publica continua respondendo;
* CA4 — evento ja cadastrado, sem modalidade gravada, e presencial (o padrao
  do schema, do modelo e da migration);
* CA5 — o online guarda o link de transmissao no lugar do endereco, e e esse
  link que vai para a agenda do Google.

Ficam de fora, de proposito, as duas lacunas da EX-02 que dependem de
decisao de produto (online sem link e formato do link): continuam como
`xfail` estrito em `test_achados_exploratorios.py`.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.evento.controller import get_servico, router as evento_router
from src.evento.model import Evento
from src.evento.schema import (
    BaseEvento,
    ModalidadeEvento,
    SituacaoEvento,
    SolicitacaoEvento,
    SolicitacaoSituacaoEvento,
    TipoEvento,
)
from src.evento.service import ServicoEvento
from src.security import obter_usuario_atual
from tests.unit.migracoes_teste import colunas_adicionadas, colunas_removidas, operacoes

LINK = "https://youtube.com/live/idb-jovem"
REVISAO_US19 = "f1e2d3c4b5a6"


def corpo(**extras) -> dict:
    inicio = datetime.now() + timedelta(days=20)
    base = {
        "nome": "Culto Jovem",
        "tipo_evento": TipoEvento.OUTROS.value,
        "data_inicio": inicio.isoformat(),
        "data_fim": (inicio + timedelta(hours=2)).isoformat(),
    }
    base.update(extras)
    return base


def presencial(**extras) -> dict:
    return corpo(local_latitude=-15.79, local_longitude=-47.88, **extras)


def online(**extras) -> dict:
    return corpo(modalidade="online", link_transmissao=LINK, **extras)


def evento_orm(**extras) -> Evento:
    inicio = datetime.now() + timedelta(days=20)
    padrao = {
        "evento_id": 1,
        "nome": "Culto Jovem",
        "tipo_evento": "Outros",
        "data_inicio": inicio,
        "data_fim": inicio + timedelta(hours=2),
        "local_latitude": -15.79,
        "local_longitude": -47.88,
        "nome_local": "Brasília",
        "calendario_evento_id": "cal-1",
        "situacao": "ativo",
        "modalidade": "presencial",
    }
    padrao.update(extras)
    return Evento(**padrao)


def evento_online_gravado() -> Evento:
    return evento_orm(
        modalidade="online",
        link_transmissao=LINK,
        local_latitude=None,
        local_longitude=None,
        nome_local=None,
    )


# Achado ao escrever esta suite. Fica como especificacao executavel, e nao
# como correcao, pelo mesmo motivo dos achados da EX-02: a correcao muda o
# contrato do PUT entre as duas pontas e depende de decidir se a edicao e
# total (modalidade obrigatoria no PUT) ou parcial (o validador nao pode
# aplicar o padrao "presencial" ao que nao veio no corpo).
DEFEITO_EDICAO_SEM_MODALIDADE = (
    "US19: PUT que omite `modalidade` num evento online apaga o link de "
    "transmissao. O validador de SolicitacaoEvento assume o padrao "
    "'presencial', atribui link_transmissao=None, e a atribuicao entra no "
    "model_dump(exclude_unset=True); o servico preserva a modalidade gravada "
    "(online), mas grava o link nulo. Correcao proposta: decidir se o PUT e "
    "total ou parcial e alinhar validador e servico. Remova o xfail quando entrar."
)


@pytest.fixture
def repositorio():
    repo = MagicMock()
    repo.salvar.side_effect = lambda evento: evento
    return repo


@pytest.fixture
def calendario():
    cal = MagicMock()
    cal.criar_evento.return_value = "cal-1"
    return cal


@pytest.fixture
def mapa():
    servico_mapa = MagicMock()
    servico_mapa.buscar_endereco_por_coordenadas.return_value = "Brasília"
    return servico_mapa


@pytest.fixture
def servico(repositorio, calendario, mapa):
    return ServicoEvento(repositorio, calendario, mapa)


@pytest.fixture
def client(servico):
    app = FastAPI()
    app.include_router(evento_router)
    app.dependency_overrides[get_servico] = lambda: servico
    app.dependency_overrides[obter_usuario_atual] = lambda: {
        "sub": "u-1",
        "realm_access": {"roles": ["admin", "admin-eventos"]},
    }
    return TestClient(app)


# ---------------------------------------------------------------------- schema


class TestNormalizacaoDaModalidade:
    """O front ja enviou a modalidade como texto e como booleano `online`."""

    @pytest.mark.parametrize(
        "enviado, esperado",
        [
            pytest.param("online", ModalidadeEvento.ONLINE, id="texto_online"),
            pytest.param("  ONLINE ", ModalidadeEvento.ONLINE, id="maiusculas_e_espacos"),
            pytest.param("presencial", ModalidadeEvento.PRESENCIAL, id="texto_presencial"),
            pytest.param("Presencial", ModalidadeEvento.PRESENCIAL, id="capitalizado"),
            pytest.param(True, ModalidadeEvento.ONLINE, id="booleano_true"),
            pytest.param(False, ModalidadeEvento.PRESENCIAL, id="booleano_false"),
            pytest.param("true", ModalidadeEvento.ONLINE, id="texto_true"),
            pytest.param("false", ModalidadeEvento.PRESENCIAL, id="texto_false"),
            pytest.param(None, ModalidadeEvento.PRESENCIAL, id="nulo"),
        ],
    )
    def test_formas_aceitas(self, enviado, esperado):
        dados = BaseEvento(**corpo(modalidade=enviado))
        assert dados.modalidade == esperado

    def test_sem_modalidade_e_presencial(self):
        """CA4 no contrato: quem nao informa a modalidade cadastra presencial."""
        assert BaseEvento(**corpo()).modalidade == ModalidadeEvento.PRESENCIAL

    @pytest.mark.parametrize("enviado", ["hibrido", "remoto", "", 1])
    def test_modalidade_fora_da_lista_e_recusada(self, enviado):
        with pytest.raises(ValidationError):
            BaseEvento(**corpo(modalidade=enviado))


class TestCadastroPorModalidade:
    """CA1 — online desobriga o endereco; presencial continua como era."""

    def test_online_sem_coordenadas_e_aceito(self):
        dados = SolicitacaoEvento(**online())

        assert dados.modalidade == ModalidadeEvento.ONLINE
        assert dados.local_latitude is None
        assert dados.local_longitude is None
        assert dados.link_transmissao == LINK

    def test_online_descarta_coordenadas_enviadas(self):
        dados = SolicitacaoEvento(**online(local_latitude=-15.79, local_longitude=-47.88))

        assert (dados.local_latitude, dados.local_longitude) == (None, None)

    @pytest.mark.parametrize(
        "coordenadas",
        [
            pytest.param({}, id="sem_nenhuma"),
            pytest.param({"local_latitude": -15.79}, id="so_latitude"),
            pytest.param({"local_longitude": -47.88}, id="so_longitude"),
        ],
    )
    def test_presencial_sem_coordenadas_e_recusado(self, coordenadas):
        with pytest.raises(ValidationError, match="presencial exige latitude e longitude"):
            SolicitacaoEvento(**corpo(modalidade="presencial", **coordenadas))

    def test_presencial_descarta_link_de_transmissao(self):
        """CA5 — o presencial mantem o local no mapa, nao um link."""
        dados = SolicitacaoEvento(**presencial(link_transmissao=LINK))

        assert dados.modalidade == ModalidadeEvento.PRESENCIAL
        assert dados.link_transmissao is None


# --------------------------------------------------------------------- servico


class TestCriarEventoOnline:

    def test_nao_consulta_o_mapa_e_grava_sem_endereco(self, servico, mapa):
        """CA3 — o online nao tem endereco, entao o servico de mapa nem e chamado."""
        evento = servico.criar_evento(SolicitacaoEvento(**online()))

        mapa.buscar_endereco_por_coordenadas.assert_not_called()
        assert evento.modalidade == "online"
        assert evento.local_latitude is None
        assert evento.local_longitude is None
        assert evento.nome_local is None
        assert evento.link_transmissao == LINK

    def test_agenda_do_google_recebe_o_link_como_local(self, servico, calendario):
        """CA5 — na agenda, o link de transmissao ocupa o lugar do endereco."""
        servico.criar_evento(SolicitacaoEvento(**online()))

        _, local = calendario.criar_evento.call_args.args
        assert local == LINK

    def test_sem_link_a_agenda_recebe_online(self, servico, calendario):
        """
        Hoje o online sem link e aceito (achado da EX-02, `xfail` a parte).
        Enquanto for, a agenda nao pode ficar com local vazio.
        """
        servico.criar_evento(SolicitacaoEvento(**corpo(modalidade="online")))

        _, local = calendario.criar_evento.call_args.args
        assert local == "Online"

    def test_grava_o_id_da_agenda(self, servico):
        evento = servico.criar_evento(SolicitacaoEvento(**online()))
        assert evento.calendario_evento_id == "cal-1"


class TestCriarEventoPresencial:

    def test_consulta_o_mapa_e_descarta_o_link(self, servico, mapa, calendario):
        evento = servico.criar_evento(SolicitacaoEvento(**presencial(link_transmissao=LINK)))

        mapa.buscar_endereco_por_coordenadas.assert_called_once_with(-15.79, -47.88)
        assert evento.modalidade == "presencial"
        assert evento.nome_local == "Brasília"
        assert evento.link_transmissao is None
        _, local = calendario.criar_evento.call_args.args
        assert local == "Brasília"


class TestTrocarModalidadeNaEdicao:

    def test_presencial_para_online_limpa_o_endereco(
        self, servico, repositorio, mapa, calendario
    ):
        repositorio.buscar_por_id.return_value = evento_orm()

        evento = servico.atualizar_evento(1, SolicitacaoEvento(**online()))

        mapa.buscar_endereco_por_coordenadas.assert_not_called()
        assert evento.modalidade == "online"
        assert evento.local_latitude is None
        assert evento.local_longitude is None
        assert evento.nome_local is None
        assert evento.link_transmissao == LINK
        calendario.atualizar_evento.assert_called_once_with("cal-1", evento, LINK)

    def test_online_para_presencial_volta_a_consultar_o_mapa(
        self, servico, repositorio, mapa, calendario
    ):
        repositorio.buscar_por_id.return_value = evento_orm(
            modalidade="online",
            link_transmissao=LINK,
            local_latitude=None,
            local_longitude=None,
            nome_local=None,
        )

        evento = servico.atualizar_evento(
            1, SolicitacaoEvento(**presencial(modalidade="presencial"))
        )

        mapa.buscar_endereco_por_coordenadas.assert_called_once_with(-15.79, -47.88)
        assert evento.modalidade == "presencial"
        assert evento.nome_local == "Brasília"
        assert evento.link_transmissao is None
        calendario.atualizar_evento.assert_called_once_with("cal-1", evento, "Brasília")

    def test_edicao_sem_modalidade_preserva_a_gravada(self, servico, repositorio, mapa):
        """
        A edicao aplica so o que veio no corpo (`exclude_unset`), como nos
        campos da US02. Um PUT que omite a modalidade nao rebaixa o online
        para presencial pelo valor padrao do schema.
        """
        repositorio.buscar_por_id.return_value = evento_online_gravado()

        evento = servico.atualizar_evento(1, SolicitacaoEvento(**presencial(nome="Novo nome")))

        assert evento.nome == "Novo nome"
        assert evento.modalidade == "online"
        assert evento.local_latitude is None
        mapa.buscar_endereco_por_coordenadas.assert_not_called()

    @pytest.mark.xfail(strict=True, reason=DEFEITO_EDICAO_SEM_MODALIDADE)
    def test_edicao_sem_modalidade_preserva_o_link_de_transmissao(
        self, servico, repositorio
    ):
        repositorio.buscar_por_id.return_value = evento_online_gravado()

        evento = servico.atualizar_evento(1, SolicitacaoEvento(**presencial(nome="Novo nome")))

        assert evento.link_transmissao == LINK

    def test_online_sem_id_da_agenda_nao_chama_o_google(
        self, servico, repositorio, calendario
    ):
        repositorio.buscar_por_id.return_value = evento_orm(calendario_evento_id=None)

        servico.atualizar_evento(1, SolicitacaoEvento(**online()))

        calendario.atualizar_evento.assert_not_called()
        repositorio.salvar.assert_called_once()


class TestSituacaoDoEventoOnline:
    """US14 sobre evento da US19: a agenda continua com o local certo."""

    def test_online_mantem_o_link_na_agenda(self, servico, repositorio, calendario):
        repositorio.buscar_por_id.return_value = evento_orm(
            modalidade="online", link_transmissao=LINK, nome_local=None
        )

        servico.alterar_situacao(1, SolicitacaoSituacaoEvento(situacao=SituacaoEvento.CANCELADO))

        _, _, local = calendario.atualizar_evento.call_args.args
        assert local == LINK

    def test_online_sem_link_usa_online(self, servico, repositorio, calendario):
        repositorio.buscar_por_id.return_value = evento_orm(
            modalidade="online", link_transmissao=None, nome_local=None
        )

        servico.alterar_situacao(1, SolicitacaoSituacaoEvento(situacao=SituacaoEvento.CANCELADO))

        _, _, local = calendario.atualizar_evento.call_args.args
        assert local == "Online"

    def test_presencial_mantem_o_endereco_na_agenda(self, servico, repositorio, calendario):
        repositorio.buscar_por_id.return_value = evento_orm()

        servico.alterar_situacao(1, SolicitacaoSituacaoEvento(situacao=SituacaoEvento.ADIADO))

        _, _, local = calendario.atualizar_evento.call_args.args
        assert local == "Brasília"


# ------------------------------------------------------------------ controller


class TestRotas:

    def test_post_online_sem_coordenadas_responde_201(self, client, repositorio):
        def salvar_com_id(evento):
            evento.evento_id = 1
            return evento

        repositorio.salvar.side_effect = salvar_com_id

        resposta = client.post("/evento/", json=online())

        assert resposta.status_code == 201, resposta.text
        corpo_resposta = resposta.json()
        assert corpo_resposta["modalidade"] == "online"
        assert corpo_resposta["link_transmissao"] == LINK
        assert corpo_resposta["local_latitude"] is None
        assert corpo_resposta["nome_local"] is None

    def test_post_presencial_sem_coordenadas_responde_422(self, client):
        resposta = client.post("/evento/", json=corpo(modalidade="presencial"))
        assert resposta.status_code == 422

    def test_put_para_presencial_sem_coordenadas_responde_422(self, client, repositorio):
        repositorio.buscar_por_id.return_value = evento_orm(modalidade="online")

        resposta = client.put("/evento/1", json=corpo(modalidade="presencial"))

        assert resposta.status_code == 422
        repositorio.salvar.assert_not_called()

    def test_modalidade_desconhecida_responde_422(self, client):
        resposta = client.post("/evento/", json=corpo(modalidade="hibrido", link_transmissao=LINK))
        assert resposta.status_code == 422

    def test_listagem_publica_com_as_duas_modalidades(self, client, repositorio):
        """CA2 e CA3 — a listagem traz a modalidade de cada evento e nao quebra
        com o online sem coordenadas."""
        repositorio.buscar_todos.return_value = [
            evento_orm(evento_id=1),
            evento_orm(
                evento_id=2,
                modalidade="online",
                link_transmissao=LINK,
                local_latitude=None,
                local_longitude=None,
                nome_local=None,
            ),
        ]

        resposta = client.get("/evento/")

        assert resposta.status_code == 200, resposta.text
        por_id = {e["evento_id"]: e for e in resposta.json()}
        assert por_id[1]["modalidade"] == "presencial"
        assert por_id[2]["modalidade"] == "online"
        assert por_id[2]["link_transmissao"] == LINK
        assert por_id[2]["local_latitude"] is None


# --------------------------------------------------- modelo e migration (CA4)


class TestEventosJaCadastradosSaoPresenciais:
    """CA4 — o que decide e o banco: `server_default`, nao o codigo Python."""

    def test_coluna_do_modelo_nasce_presencial_e_nao_aceita_nulo(self):
        coluna = Evento.__table__.c.modalidade

        assert coluna.nullable is False
        assert "presencial" in str(coluna.server_default.arg)

    def test_migration_cria_modalidade_com_padrao_presencial(self):
        colunas = colunas_adicionadas(operacoes(REVISAO_US19), "evento")

        assert set(colunas) == {"modalidade", "link_transmissao"}
        assert colunas["modalidade"].nullable is False
        assert "presencial" in str(colunas["modalidade"].server_default.arg)
        assert colunas["link_transmissao"].nullable is True

    def test_migration_e_reversivel(self):
        removidas = colunas_removidas(operacoes(REVISAO_US19, "downgrade"), "evento")
        assert removidas == {"modalidade", "link_transmissao"}

    def test_colunas_da_migration_existem_no_modelo(self):
        colunas = colunas_adicionadas(operacoes(REVISAO_US19), "evento")
        assert set(colunas) <= set(Evento.__table__.c.keys())
