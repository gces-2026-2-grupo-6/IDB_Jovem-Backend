"""Achados da primeira sessão de testes exploratórios (Sprint 4).

Nenhum dos defeitos abaixo apareceu em três sprints de suíte verde, e nenhum
apareceria: a cobertura da linha é 99,23% e todas estas linhas estão cobertas.
O que faltava não era execução, era alguém perguntar o que a resposta carrega.

Os dois primeiros nasceram como especificação executável — `xfail` estrito,
no formato da Sprint 3 — e **os defeitos foram corrigidos na mesma sprint**:
os marcadores saíram e os testes agora são regressão, que é o destino certo
de uma especificação cumprida. O terceiro é teste verde desde o início: trava
um comportamento que hoje está certo por decisão explícita da equipe e não
pode mudar sem que se perceba.

Sessão EX-01 (superfície de autenticação e integração com o Google),
registrada no relatório da Sprint 4.
"""

import io
import contextlib
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from src.main import app
from src.auth.controller import callback_google
from src.database import obter_banco
from src.security import obter_usuario_atual


SEGREDO_DE_TESTE = "rt-ESTE-VALOR-NAO-PODE-VAZAR"


def _requisicao_com_sessao_valida():
    requisicao = MagicMock()
    requisicao.session = {
        "google_estado": "state-123",
        "google_verificador_codigo": "verifier-123",
    }
    return requisicao


def _tokens_do_google():
    return {
        "access_token": "at-123",
        "refresh_token": SEGREDO_DE_TESTE,
        "expires_in": 3599,
    }


def test_callback_do_google_nao_devolve_o_refresh_token_na_resposta():
    """A resposta do callback não pode carregar credencial de longa duração.

    O access_token expira em uma hora; o refresh_token não expira sozinho.
    Quem obtiver o segundo fala com a conta Google do projeto até alguém
    revogar — e ninguém vai revogar, porque não há como saber que vazou.

    O callback é uma rota GET: a URL completa, com o `code`, passa por
    histórico de navegador, por log de proxy e pelo Referer. Devolver o
    refresh_token nessa resposta amplia um segredo que já circula demais.
    """
    with patch("src.auth.controller.ServicoAuth") as ServicoFalso:
        ServicoFalso.return_value.trocar_codigo_por_tokens.return_value = (
            _tokens_do_google()
        )
        resposta = callback_google(
            request=_requisicao_com_sessao_valida(), codigo="code-123"
        )

    assert SEGREDO_DE_TESTE not in str(resposta), (
        "o refresh_token do Google volta no corpo da resposta de /auth/callback"
    )


def test_callback_do_google_nao_imprime_o_refresh_token_no_log():
    """Credencial não pode ir para o log do contêiner.

    O log de produção é lido por qualquer pessoa com acesso à VPS, é copiado
    em diagnóstico e sobrevive ao contêiner. Um segredo que entra ali tem que
    ser considerado comprometido.
    """
    saida = io.StringIO()
    with patch("src.auth.controller.ServicoAuth") as ServicoFalso:
        ServicoFalso.return_value.trocar_codigo_por_tokens.return_value = (
            _tokens_do_google()
        )
        with contextlib.redirect_stdout(saida):
            callback_google(
                request=_requisicao_com_sessao_valida(), codigo="code-123"
            )

    assert SEGREDO_DE_TESTE not in saida.getvalue(), (
        "o refresh_token do Google é impresso no stdout do contêiner"
    )


@pytest.fixture
def banco_falso():
    banco = MagicMock()
    banco.query.return_value.all.return_value = []
    return banco


@pytest.fixture
def cliente(banco_falso):
    app.dependency_overrides[obter_banco] = lambda: banco_falso
    with patch(
        "src.calendario.service.ServicoCalendario._obter_token_valido",
        return_value=None,
    ):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()


def _usuario_com(papeis):
    return lambda: {"sub": "usr-exploratorio", "realm_access": {"roles": papeis}}


def test_admin_sem_papel_de_setor_ainda_alcanca_todos_os_setores(cliente):
    """Porta de retrocompatibilidade da US03, afirmada de propósito.

    `verificar_permissao_setor` libera o administrador que não tem nenhum
    papel de setor: a regra está escrita e comentada em src/security.py como
    retrocompatibilidade, para não trancar do lado de fora quem já era
    administrador antes de a US03 existir.

    Está certo hoje e por isso o teste é verde. O que ele impede é a porta
    continuar aberta sem ninguém notar. O risco é operacional e ficou maior
    agora que a cliente cria administradores sozinha pelo console do
    Keycloak: criar o usuário com o papel `admin` e esquecer o papel de setor
    não produz um administrador limitado — produz um com acesso a tudo, sem
    nenhum aviso na tela.

    Quando a equipe decidir fechar a porta, este teste quebra. É esse o
    objetivo: que fechar seja um ato deliberado, com o registro de que o
    comportamento mudou.
    """
    app.dependency_overrides[obter_usuario_atual] = _usuario_com(["admin"])

    respostas = {
        "eventos": cliente.get("/evento/"),
        "voluntarios": cliente.get("/voluntarios/"),
    }
    for setor, resposta in respostas.items():
        assert resposta.status_code != 403, (
            f"admin sem papel de setor foi barrado em {setor}: "
            "a porta de retrocompatibilidade foi fechada — se foi de "
            "propósito, atualize este teste e o registro da US03"
        )


# --------------------------------------------------------------------------
# Sessão EX-02 — as melhorias da Sprint 3 em uso
#
# Carta: investigar o que o sistema aceita gravar nas histórias entregues na
# Sprint 3, procurando estado que o cadastro permite e que a tela não tem como
# representar.
#
# Os três achados abaixo são regra de produto das histórias dos trios, não
# defeito de segurança. Ficam como especificação executável — `xfail` estrito,
# com a correção proposta escrita no motivo — em vez de mudança de
# comportamento: validar entrada que o front já envia muda o contrato entre as
# duas pontas, e essa verificação exige a pilha integrada de pé.
# --------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "US14: PATCH /evento/{id}/situacao aceita adiar um evento para uma "
        "data no passado. Não há validação em SolicitacaoSituacaoEvento nem "
        "em ServicoEvento.alterar_situacao — `nova_data` é gravada como veio. "
        "Correção proposta: um model_validator em SolicitacaoSituacaoEvento "
        "recusando nova_data anterior a agora, do mesmo jeito que "
        "validar_datas já recusa data_fim antes de data_inicio."
    ),
)
def test_us14_adiar_para_data_no_passado_e_recusado():
    """Adiar para ontem não é um estado que a tela saiba representar.

    O criador do evento marca "adiado" e informa quando será. Uma data no
    passado não descreve nada: o visitante lê "adiado para 10/03/2020" e não
    sabe se o evento já aconteceu, se foi cancelado ou se alguém errou a
    digitação.

    O projeto já recusa a incoerência irmã — `validar_datas` barra data de fim
    antes da data de início. Esta ficou de fora.
    """
    from datetime import datetime, timedelta

    from src.evento.schema import SolicitacaoSituacaoEvento

    ontem = datetime.now() - timedelta(days=1)
    with pytest.raises((ValueError, ValidationError)):
        SolicitacaoSituacaoEvento(situacao="adiado", nova_data=ontem)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "US19, CA5: o evento online é aceito sem link de transmissão. O "
        "critério diz que o link é o que o online guarda 'no lugar do "
        "endereço', e o endereço é obrigatório no presencial — a simetria não "
        "foi implementada. Correção proposta: estender "
        "_validar_local_por_modalidade para exigir link_transmissao quando a "
        "modalidade for online, como já exige latitude e longitude no "
        "presencial."
    ),
)
def test_us19_evento_online_exige_link_de_transmissao():
    """Online sem link deixa o visitante sem para onde ir.

    O presencial que chega sem coordenadas é recusado com "Evento presencial
    exige latitude e longitude". O online que chega sem link é aceito, e o
    card mostra um selo "Online" que não leva a lugar nenhum.
    """
    from datetime import datetime, timedelta

    from src.evento.schema import SolicitacaoEvento

    inicio = datetime.now() + timedelta(days=10)
    with pytest.raises((ValueError, ValidationError)):
        SolicitacaoEvento(
            nome="Conferência online sem link",
            descricao="Sem link de transmissão.",
            tipo_evento="Conferência",
            modalidade="online",
            data_inicio=inicio,
            data_fim=inicio + timedelta(hours=2),
        )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "US19: link_transmissao é `str | None` sem validação nenhuma, "
        "enquanto o link do material (US11) passa por _link_http em "
        "src/material/schema.py. A mesma equipe validou um e não o outro, e a "
        "regra que existe hoje mora só no formulário do front — quem chama a "
        "API direto grava qualquer texto. Correção proposta: reaproveitar o "
        "field_validator de material/schema.py em link_transmissao."
    ),
)
def test_us19_link_de_transmissao_precisa_ser_endereco_http():
    """O que vale para o material tem que valer para a transmissão.

    Sem isso, a regra existe só na tela: o formulário recusa, a API aceita, e
    basta uma chamada direta para o card do evento publicar um link quebrado.
    """
    from datetime import datetime, timedelta

    from src.evento.schema import SolicitacaoEvento

    inicio = datetime.now() + timedelta(days=10)
    with pytest.raises((ValueError, ValidationError)):
        SolicitacaoEvento(
            nome="Conferência com link inválido",
            descricao="O link não é um endereço.",
            tipo_evento="Conferência",
            modalidade="online",
            link_transmissao="isto nao e um link",
            data_inicio=inicio,
            data_fim=inicio + timedelta(hours=2),
        )
