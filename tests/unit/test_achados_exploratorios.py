"""Achados da primeira sessão de testes exploratórios (Sprint 4).

Nenhum dos defeitos abaixo apareceu em três sprints de suíte verde, e nenhum
apareceria: a cobertura da linha é 99,23% e todas estas linhas estão cobertas.
O que faltava não era execução, era alguém perguntar o que a resposta carrega.

Dois registros são especificação executável, no mesmo formato da Sprint 3:
`xfail` estrito, que falha enquanto o defeito existe e vira `XPASS(strict)` —
isto é, build vermelha — no dia em que alguém "consertar" sem tirar o
marcador. O terceiro é teste verde: trava um comportamento que hoje está
certo por decisão explícita da equipe e não pode mudar sem que se perceba.

Sessão EX-01 (superfície de autenticação e integração com o Google),
registrada no relatório da Sprint 4.
"""

import io
import contextlib
from unittest.mock import MagicMock, patch

import pytest
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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "GET /auth/callback devolve o payload inteiro do Google no corpo da "
        "resposta, incluindo o refresh_token, que é credencial de longa "
        "duração da conta Google do projeto (Drive, Calendar e Forms). Veio "
        "de conveniência de desenvolvimento — a própria resposta diz 'Copie o "
        "refresh_token do terminal/tela' — e foi para produção. Ao corrigir, "
        "o teste tests/unit/test_auth_controller.py::test_callback_google_"
        "sucesso também precisa mudar: ele afirma hoje que os tokens voltam "
        "em 'dados'."
    ),
)
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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "src/auth/controller.py imprime o refresh_token em stdout. Em "
        "produção stdout é o log do contêiner: `docker compose logs "
        "jovem-backend` mostra a credencial em texto puro, e o log fica "
        "retido muito depois de a sessão acabar."
    ),
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
