"""
US14 — Marcar evento como cancelado ou adiado.

O evento continua no site com aviso (nada é apagado), o adiado pode trazer a
nova data e ninguém é avisado automaticamente. O front marca e desmarca por
PATCH /evento/{id}/situacao; o PUT completo também aceita os campos.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.calendario.service import titulo_na_agenda
from src.evento.controller import router as evento_router, get_servico
from src.evento.model import Evento
from src.evento.schema import (
    RespostaEvento,
    SituacaoEvento,
    SolicitacaoEvento,
    SolicitacaoSituacaoEvento,
    TipoEvento,
)
from src.evento.service import ServicoEvento
from src.security import obter_usuario_atual

NOVA_DATA = datetime(2027, 4, 10, 9, 0, tzinfo=timezone.utc)

EVENTO = {
    "nome": "Congresso Nacional",
    "tipo_evento": TipoEvento.CONFERENCIA,
    "data_inicio": datetime.now() + timedelta(days=10),
    "data_fim": datetime.now() + timedelta(days=11),
    "local_latitude": -15.79,
    "local_longitude": -47.88,
}


@pytest.fixture
def repositorio():
    repo = MagicMock()
    repo.salvar.side_effect = lambda evento: evento
    return repo


@pytest.fixture
def calendario():
    return MagicMock()


@pytest.fixture
def servico(repositorio, calendario):
    mapa = MagicMock()
    mapa.buscar_endereco_por_coordenadas.return_value = "Brasília"
    return ServicoEvento(repositorio, calendario, mapa)


def evento_salvo(**campos):
    padrao = {
        "evento_id": 1,
        "nome": "Congresso Nacional",
        "calendario_evento_id": "cal-1",
        "nome_local": "Brasília",
        "situacao": "ativo",
        "nova_data": None,
        "data_inicio": EVENTO["data_inicio"],
        "data_fim": EVENTO["data_fim"],
        "local_latitude": -15.79,
        "local_longitude": -47.88,
    }
    return Evento(**{**padrao, **campos})


# ---------------------------------------------------------------------- schema


class TestSchema:

    def test_evento_sem_situacao_e_ativo(self):
        assert SolicitacaoEvento(**EVENTO).situacao is SituacaoEvento.ATIVO

    def test_situacao_fora_da_lista_e_recusada(self):
        with pytest.raises(ValidationError):
            SolicitacaoSituacaoEvento(situacao="suspenso")

    def test_adiado_aceita_nova_data(self):
        dados = SolicitacaoSituacaoEvento(situacao="adiado", nova_data=NOVA_DATA)
        assert dados.nova_data == NOVA_DATA

    def test_adiado_sem_nova_data_e_permitido(self):
        """CA4: a nova data aparece só quando já existir."""
        assert SolicitacaoSituacaoEvento(situacao="adiado").nova_data is None

    @pytest.mark.parametrize("situacao", ["ativo", "cancelado"])
    def test_nova_data_e_descartada_fora_do_adiado(self, situacao):
        dados = SolicitacaoSituacaoEvento(situacao=situacao, nova_data=NOVA_DATA)
        assert dados.nova_data is None

    def test_resposta_publica_situacao_e_nova_data(self):
        resposta = RespostaEvento.model_validate(
            evento_salvo(situacao="adiado", nova_data=NOVA_DATA)
        )
        assert resposta.situacao is SituacaoEvento.ADIADO
        assert resposta.nova_data == NOVA_DATA


# --------------------------------------------------------------------- serviço


class TestAlterarSituacao:

    @pytest.mark.parametrize("situacao", ["cancelado", "adiado"])
    def test_marca_sem_apagar_nada(self, servico, repositorio, situacao):
        """CA3: evento, inscrições e fotos continuam guardados."""
        repositorio.buscar_por_id.return_value = evento_salvo()

        evento = servico.alterar_situacao(1, SolicitacaoSituacaoEvento(situacao=situacao))

        assert evento.situacao == situacao
        repositorio.salvar.assert_called_once()
        repositorio.deletar.assert_not_called()

    def test_adiado_guarda_a_nova_data(self, servico, repositorio):
        repositorio.buscar_por_id.return_value = evento_salvo()

        evento = servico.alterar_situacao(
            1, SolicitacaoSituacaoEvento(situacao="adiado", nova_data=NOVA_DATA)
        )

        assert evento.nova_data == NOVA_DATA

    def test_desfazer_volta_para_ativo_e_limpa_a_nova_data(self, servico, repositorio):
        """CA1: a marcação pode ser desfeita."""
        repositorio.buscar_por_id.return_value = evento_salvo(
            situacao="adiado", nova_data=NOVA_DATA
        )

        evento = servico.alterar_situacao(1, SolicitacaoSituacaoEvento(situacao="ativo"))

        assert evento.situacao == "ativo"
        assert evento.nova_data is None

    def test_atualiza_a_agenda_do_google(self, servico, repositorio, calendario):
        repositorio.buscar_por_id.return_value = evento_salvo()

        servico.alterar_situacao(1, SolicitacaoSituacaoEvento(situacao="cancelado"))

        calendario.atualizar_evento.assert_called_once()
        assert calendario.atualizar_evento.call_args.args[0] == "cal-1"

    def test_evento_fora_da_agenda_nao_chama_o_google(self, servico, repositorio, calendario):
        repositorio.buscar_por_id.return_value = evento_salvo(calendario_evento_id=None)

        servico.alterar_situacao(1, SolicitacaoSituacaoEvento(situacao="cancelado"))

        calendario.atualizar_evento.assert_not_called()

    def test_falha_na_agenda_nao_desfaz_a_marcacao(self, servico, repositorio, calendario):
        repositorio.buscar_por_id.return_value = evento_salvo()
        calendario.atualizar_evento.side_effect = RuntimeError("Google fora do ar")

        evento = servico.alterar_situacao(1, SolicitacaoSituacaoEvento(situacao="cancelado"))

        assert evento.situacao == "cancelado"
        repositorio.salvar.assert_called_once()

    def test_evento_inexistente(self, servico, repositorio):
        repositorio.buscar_por_id.return_value = None

        with pytest.raises(ValueError, match="Evento não encontrado"):
            servico.alterar_situacao(9, SolicitacaoSituacaoEvento(situacao="cancelado"))


class TestPutCompleto:

    def test_put_sem_situacao_nao_mexe_no_adiamento(self, servico, repositorio):
        """
        Editar a descrição de um evento adiado pelo formulário completo não
        pode apagar a nova data nem voltar o evento para ativo.
        """
        repositorio.buscar_por_id.return_value = evento_salvo(
            situacao="adiado", nova_data=NOVA_DATA
        )

        evento = servico.atualizar_evento(
            1, SolicitacaoEvento(**EVENTO, descricao="Nova descrição")
        )

        assert evento.situacao == "adiado"
        assert evento.nova_data == NOVA_DATA

    def test_put_que_cancela_limpa_a_nova_data(self, servico, repositorio):
        repositorio.buscar_por_id.return_value = evento_salvo(
            situacao="adiado", nova_data=NOVA_DATA
        )

        evento = servico.atualizar_evento(
            1, SolicitacaoEvento(**EVENTO, situacao="cancelado")
        )

        assert evento.situacao == "cancelado"
        assert evento.nova_data is None

    def test_cadastro_ativo_ignora_nova_data(self, servico, calendario):
        calendario.criar_evento.return_value = "cal-9"

        evento = servico.criar_evento(SolicitacaoEvento(**EVENTO, nova_data=NOVA_DATA))

        assert evento.situacao == SituacaoEvento.ATIVO
        assert evento.nova_data is None

    def test_cadastro_ja_adiado_guarda_a_nova_data(self, servico, calendario):
        calendario.criar_evento.return_value = "cal-9"

        evento = servico.criar_evento(
            SolicitacaoEvento(**EVENTO, situacao="adiado", nova_data=NOVA_DATA)
        )

        assert evento.nova_data == NOVA_DATA


# ------------------------------------------------------------------ agenda Google


class TestTituloNaAgenda:

    @pytest.mark.parametrize(
        "situacao,titulo",
        [
            ("cancelado", "[CANCELADO] Congresso Nacional"),
            ("adiado", "[ADIADO] Congresso Nacional"),
            (SituacaoEvento.ADIADO, "[ADIADO] Congresso Nacional"),
            ("ativo", "Congresso Nacional"),
            (None, "Congresso Nacional"),
        ],
    )
    def test_aviso_no_titulo(self, situacao, titulo):
        assert titulo_na_agenda(evento_salvo(situacao=situacao)) == titulo

    def test_objeto_sem_situacao_usa_so_o_nome(self):
        evento = MagicMock(spec=["nome"])
        evento.nome = "Retiro"
        assert titulo_na_agenda(evento) == "Retiro"


# ----------------------------------------------------- PATCH /evento/{id}/situacao


def _client(servico_mock, papeis):
    app = FastAPI()
    app.include_router(evento_router)
    app.dependency_overrides[get_servico] = lambda: servico_mock
    app.dependency_overrides[obter_usuario_atual] = lambda: {
        "sub": "u-1",
        "realm_access": {"roles": papeis},
    }
    return TestClient(app)


class TestRotaSituacao:

    def test_admin_de_eventos_cancela(self):
        servico_mock = MagicMock()
        servico_mock.alterar_situacao.return_value = evento_salvo(situacao="cancelado")

        resposta = _client(servico_mock, ["admin", "admin-eventos"]).patch(
            "/evento/1/situacao", json={"situacao": "cancelado"}
        )

        assert resposta.status_code == 200
        assert resposta.json()["situacao"] == "cancelado"
        assert resposta.json()["nova_data"] is None

    def test_adiado_com_nova_data(self):
        servico_mock = MagicMock()
        servico_mock.alterar_situacao.return_value = evento_salvo(
            situacao="adiado", nova_data=NOVA_DATA
        )

        resposta = _client(servico_mock, ["superadmin"]).patch(
            "/evento/1/situacao",
            json={"situacao": "adiado", "nova_data": "2027-04-10T09:00:00Z"},
        )

        assert resposta.status_code == 200
        enviado = servico_mock.alterar_situacao.call_args.args[1]
        assert enviado.nova_data == NOVA_DATA

    def test_admin_de_outro_setor_e_recusado(self):
        resposta = _client(MagicMock(), ["admin", "admin-produtos"]).patch(
            "/evento/1/situacao", json={"situacao": "cancelado"}
        )

        assert resposta.status_code == 403

    def test_evento_inexistente_responde_404(self):
        servico_mock = MagicMock()
        servico_mock.alterar_situacao.side_effect = ValueError("Evento não encontrado.")

        resposta = _client(servico_mock, ["superadmin"]).patch(
            "/evento/9/situacao", json={"situacao": "cancelado"}
        )

        assert resposta.status_code == 404

    def test_situacao_invalida_responde_422(self):
        resposta = _client(MagicMock(), ["superadmin"]).patch(
            "/evento/1/situacao", json={"situacao": "suspenso"}
        )

        assert resposta.status_code == 422
