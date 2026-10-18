"""
Busca de evento por nome, contra o Postgres de verdade.

`RepositorioEvento.pesquisar_por_nome` usa `similarity(nome, :termo)`, funcao da
extensao **pg_trgm** do Postgres. A suite unitaria roda em SQLite, onde essa
funcao nao existe: a consulta aparece como coberta no relatorio, mas nunca e
executada. Trocar o limiar, o operador ou o nome da coluna passa por todos os
testes e so quebra em producao, na primeira busca.

Estes testes rodam no job de endpoint, que ja sobe Postgres e a aplicacao em
container. Sao marcados com `endpoint`, entao ficam fora da suite rapida.

Se falharem com "function similarity does not exist", a extensao pg_trgm nao
esta instalada no banco — e esse e justamente um erro que nenhum teste pegava
antes: a rota responde 500 e a busca do site para de funcionar.
"""

import httpx
import pytest

pytestmark = pytest.mark.endpoint

BASE_URL = "http://localhost:8000"


def buscar(termo: str) -> httpx.Response:
    return httpx.get(f"{BASE_URL}/evento/buscar", params={"termo": termo})


class TestConsultaDeBusca:

    def test_busca_responde_sem_erro_de_banco(self):
        """
        O caso que importa: a consulta roda no Postgres. Um 500 aqui significa
        extensao ausente, funcao inexistente ou SQL quebrado.
        """
        resposta = buscar("congresso")
        assert resposta.status_code == 200, resposta.text
        assert isinstance(resposta.json(), list)

    def test_termo_sem_resultado_devolve_lista_vazia(self):
        resposta = buscar("zzz-termo-que-nao-existe-zzz")
        assert resposta.status_code == 200
        assert resposta.json() == []

    @pytest.mark.parametrize(
        "termo",
        ["Congresso", "congresso", "CONGRESSO", "congreso", "  congresso  "],
        ids=["normal", "minusculas", "maiusculas", "com-erro-de-digitacao", "com-espacos"],
    )
    def test_variacoes_do_termo_nao_quebram_a_consulta(self, termo):
        """
        A busca existe justamente para tolerar variacao de grafia — e o
        `similarity` e quem faz isso. Qualquer uma destas formas precisa
        responder 200.
        """
        assert buscar(termo).status_code == 200

    @pytest.mark.parametrize(
        "termo",
        ["%%", "__", "''", "' OR 1=1 --", "100%", "a%b"],
        ids=["curinga-porcento", "curinga-underline", "aspas", "injecao",
             "porcento-no-fim", "porcento-no-meio"],
    )
    def test_caracteres_especiais_nao_quebram_a_consulta(self, termo):
        """
        O termo entra em `ILIKE '%termo%'`. Curinga e aspa precisam ser tratados
        como texto, nao como parte da consulta — e a tentativa de injecao tem
        que voltar como busca sem resultado, nunca como erro de banco.
        """
        resposta = buscar(termo)
        assert resposta.status_code == 200, resposta.text
        assert isinstance(resposta.json(), list)

    @pytest.mark.parametrize("termo", ["", "a"], ids=["vazio", "uma-letra"])
    def test_termo_curto_e_recusado_com_422(self, termo):
        """A rota declara `min_length=2`. Isto fixa o contrato."""
        assert buscar(termo).status_code == 422
