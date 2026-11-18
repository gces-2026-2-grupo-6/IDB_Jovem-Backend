"""
US02 (RF11) — Informações completas do evento.

Valida os cinco novos campos opcionais do evento:
- vagas
- contato_responsavel
- valor_investimento
- link_pagamento
- link_regulamento
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.evento.controller import get_servico, router as evento_router
from src.evento.model import Evento
from src.evento.schema import RespostaEvento, SolicitacaoEvento, TipoEvento
from src.evento.service import ServicoEvento
from src.security import obter_usuario_atual


CAMPOS_US02 = {
    "vagas": 250,
    "contato_responsavel": "(61) 99999-0000",
    "valor_investimento": "R$ 180,00",
    "link_pagamento": "https://pagamento.test/congresso",
    "link_regulamento": "https://drive.google.com/file/d/REG/view",
}


def payload_base(**extras) -> dict:
    inicio = datetime.now() + timedelta(days=15)
    fim = inicio + timedelta(days=2)
    base = {
        "nome": "Congresso Nacional",
        "tipo_evento": TipoEvento.CONFERENCIA.value,
        "descricao": "Evento completo",
        "data_inicio": inicio.isoformat(),
        "data_fim": fim.isoformat(),
        "local_latitude": -15.79,
        "local_longitude": -47.88,
    }
    base.update(extras)
    return base


def evento_orm(**extras) -> Evento:
    inicio = datetime.now() + timedelta(days=15)
    fim = inicio + timedelta(days=2)
    padrao = {
        "evento_id": 1,
        "nome": "Congresso Nacional",
        "tipo_evento": "Conferência",
        "descricao": "Evento completo",
        "data_inicio": inicio,
        "data_fim": fim,
        "local_latitude": -15.79,
        "local_longitude": -47.88,
        "nome_local": "Brasília",
        "calendario_evento_id": "cal-1",
        "situacao": "ativo",
        "modalidade": "presencial",
    }
    padrao.update(extras)
    return Evento(**padrao)


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
def servico(repositorio, calendario):
    mapa = MagicMock()
    mapa.buscar_endereco_por_coordenadas.return_value = "Brasília"
    return ServicoEvento(repositorio, calendario, mapa)


@pytest.fixture
def client(servico):
    app = FastAPI()
    app.include_router(evento_router)
    app.dependency_overrides[get_servico] = lambda: servico
    app.dependency_overrides[obter_usuario_atual] = lambda: {
        "sub": "u-1",
        "realm_access": {"roles": ["superadmin"]},
    }
    return TestClient(app)


# ---------------------------------------------------------------------- schema


class TestSchemaUS02:

    def test_aceita_todos_os_cinco_campos_opcionais(self):
        dados = SolicitacaoEvento(**payload_base(**CAMPOS_US02))

        assert dados.vagas == 250
        assert dados.contato_responsavel == "(61) 99999-0000"
        assert dados.valor_investimento == "R$ 180,00"
        assert dados.link_pagamento == "https://pagamento.test/congresso"
        assert dados.link_regulamento == "https://drive.google.com/file/d/REG/view"

    def test_campos_opcionais_ausentes_nao_bloqueiam(self):
        dados = SolicitacaoEvento(**payload_base())

        assert dados.vagas is None
        assert dados.contato_responsavel is None
        assert dados.valor_investimento is None
        assert dados.link_pagamento is None
        assert dados.link_regulamento is None

    def test_aceita_vagas_zero(self):
        dados = SolicitacaoEvento(**payload_base(vagas=0))
        assert dados.vagas == 0

    def test_recusa_vagas_negativas(self):
        with pytest.raises(ValidationError):
            SolicitacaoEvento(**payload_base(vagas=-1))

    def test_resposta_evento_serializa_os_cinco_campos(self):
        resposta = RespostaEvento.model_validate(evento_orm(**CAMPOS_US02))

        assert resposta.vagas == 250
        assert resposta.contato_responsavel == "(61) 99999-0000"
        assert resposta.valor_investimento == "R$ 180,00"
        assert resposta.link_pagamento == "https://pagamento.test/congresso"
        assert resposta.link_regulamento == "https://drive.google.com/file/d/REG/view"

    def test_resposta_evento_aceita_campos_nulos(self):
        resposta = RespostaEvento.model_validate(evento_orm())

        assert resposta.vagas is None
        assert resposta.contato_responsavel is None
        assert resposta.valor_investimento is None
        assert resposta.link_pagamento is None
        assert resposta.link_regulamento is None


# --------------------------------------------------------------------- serviço


class TestServicoUS02:

    def test_criar_evento_persiste_os_cinco_campos(self, servico, repositorio):
        dados = SolicitacaoEvento(**payload_base(**CAMPOS_US02))

        resultado = servico.criar_evento(dados)

        assert resultado.vagas == 250
        assert resultado.contato_responsavel == "(61) 99999-0000"
        assert resultado.valor_investimento == "R$ 180,00"
        assert resultado.link_pagamento == "https://pagamento.test/congresso"
        assert resultado.link_regulamento == "https://drive.google.com/file/d/REG/view"
        assert repositorio.salvar.called

    def test_criar_evento_sem_campos_us02_nao_falha(self, servico):
        dados = SolicitacaoEvento(**payload_base())

        resultado = servico.criar_evento(dados)

        assert resultado.vagas is None
        assert resultado.contato_responsavel is None
        assert resultado.valor_investimento is None
        assert resultado.link_pagamento is None
        assert resultado.link_regulamento is None

    def test_atualizar_evento_atualiza_e_limpa_campos_us02(self, servico, repositorio):
        repositorio.buscar_por_id.return_value = evento_orm()
        mudancas = SolicitacaoEvento(**payload_base(**CAMPOS_US02))

        atualizado = servico.atualizar_evento(1, mudancas)

        assert atualizado.vagas == 250
        assert atualizado.contato_responsavel == "(61) 99999-0000"
        assert atualizado.valor_investimento == "R$ 180,00"
        assert atualizado.link_pagamento == "https://pagamento.test/congresso"
        assert atualizado.link_regulamento == "https://drive.google.com/file/d/REG/view"

        limpeza = SolicitacaoEvento(
            **payload_base(
                vagas=None,
                contato_responsavel=None,
                valor_investimento=None,
                link_pagamento=None,
                link_regulamento=None,
            )
        )
        limpo = servico.atualizar_evento(1, limpeza)

        assert limpo.vagas is None
        assert limpo.contato_responsavel is None
        assert limpo.valor_investimento is None
        assert limpo.link_pagamento is None
        assert limpo.link_regulamento is None


# ------------------------------------------------------------------ controller


class TestControllerUS02:

    def test_post_evento_retorna_os_cinco_campos(self, client, repositorio):
        def salvar_com_id(ev):
            ev.evento_id = 1
            return ev

        repositorio.salvar.side_effect = salvar_com_id

        resposta = client.post("/evento/", json=payload_base(**CAMPOS_US02))

        assert resposta.status_code == 201
        corpo = resposta.json()
        assert corpo["vagas"] == 250
        assert corpo["contato_responsavel"] == "(61) 99999-0000"
        assert corpo["valor_investimento"] == "R$ 180,00"
        assert corpo["link_pagamento"] == "https://pagamento.test/congresso"
        assert corpo["link_regulamento"] == "https://drive.google.com/file/d/REG/view"

    def test_post_evento_com_vagas_negativas_retorna_422(self, client):
        resposta = client.post("/evento/", json=payload_base(vagas=-5))
        assert resposta.status_code == 422

    def test_put_evento_atualiza_os_cinco_campos(self, client, repositorio):
        repositorio.buscar_por_id.return_value = evento_orm()

        resposta = client.put("/evento/1", json=payload_base(**CAMPOS_US02))

        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["vagas"] == 250
        assert corpo["contato_responsavel"] == "(61) 99999-0000"
        assert corpo["valor_investimento"] == "R$ 180,00"
        assert corpo["link_pagamento"] == "https://pagamento.test/congresso"
        assert corpo["link_regulamento"] == "https://drive.google.com/file/d/REG/view"

    def test_get_evento_por_id_expoe_os_cinco_campos(self, client, repositorio):
        repositorio.buscar_por_id.return_value = evento_orm(**CAMPOS_US02)

        resposta = client.get("/evento/1")

        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["vagas"] == 250
        assert corpo["contato_responsavel"] == "(61) 99999-0000"
        assert corpo["valor_investimento"] == "R$ 180,00"
        assert corpo["link_pagamento"] == "https://pagamento.test/congresso"
        assert corpo["link_regulamento"] == "https://drive.google.com/file/d/REG/view"
