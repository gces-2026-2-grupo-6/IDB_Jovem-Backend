"""
O back-end que entrou depois da Sprint 3, gravando e relendo no Postgres.

Mesma licao de `test_sprint3_postgres.py`: a suite unitaria roda em SQLite e
o que so existe no Postgres — a migration aplicada, o `server_default`, o
`JSON` — aparece como coberto sem nunca ter sido executado. A Sprint 4
registrou duas lacunas desse tipo como pendentes:

- "Nenhum teste de endpoint cobre `/pedido`" (US21);
- as colunas da US02 "precisam ser conferidas antes de dar a integracao por
  concluida".

E a US22 entrou depois do registro da sprint, tambem sem teste contra o
banco de producao.

Nenhum teste aqui depende da internet: eventos sao online (o presencial
consulta o servico de enderecos) e a sincronizacao de pedidos so e chamada
nos caminhos que respondem antes de falar com o Google. Os tokens vem do
emissor de teste descrito em `conftest.py`.
"""

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.endpoint

BRASILIA = timezone(timedelta(hours=-3))

CAMPOS_US02 = {
    "vagas": 120,
    "contato_responsavel": "(61) 98888-0000",
    "valor_investimento": "R$ 90,00",
    "link_pagamento": "https://exemplo.invalid/pagamento",
    "link_regulamento": "https://exemplo.invalid/regulamento.pdf",
}


def _evento_online(**extras) -> dict:
    inicio = datetime(2027, 8, 14, 19, 0, tzinfo=BRASILIA)
    corpo = {
        "nome": "Congresso de endpoint",
        "tipo_evento": "Conferência",
        "descricao": "Criado pelos testes de endpoint; pode ser apagado.",
        "modalidade": "online",
        "link_transmissao": "https://exemplo.invalid/ao-vivo",
        "data_inicio": inicio.isoformat(),
        "data_fim": (inicio + timedelta(hours=3)).isoformat(),
    }
    corpo.update(extras)
    return corpo


# ------------------------------------------------------------------ US02


@pytest.fixture
def evento_completo(superadmin):
    resposta = superadmin.post("/evento/", json=_evento_online(**CAMPOS_US02))
    assert resposta.status_code == 201, resposta.text
    criado = resposta.json()
    yield criado
    superadmin.delete(f"/evento/{criado['evento_id']}")


class TestInformacoesCompletasDoEvento:
    """US02 / RF11 — as cinco colunas so existem se a migration rodou."""

    def test_os_cinco_campos_voltam_na_leitura(self, anonimo, evento_completo):
        """CA3 — o visitante recebe as informacoes, sem login."""
        relido = anonimo.get(f"/evento/{evento_completo['evento_id']}")

        assert relido.status_code == 200, relido.text
        corpo = relido.json()
        for campo, valor in CAMPOS_US02.items():
            assert corpo[campo] == valor, campo

    def test_campos_omitidos_nao_bloqueiam_a_criacao(self, superadmin):
        """CA2 — opcionais: o evento nasce com os cinco nulos."""
        resposta = superadmin.post("/evento/", json=_evento_online())
        assert resposta.status_code == 201, resposta.text
        criado = resposta.json()
        try:
            for campo in CAMPOS_US02:
                assert criado[campo] is None, campo
        finally:
            superadmin.delete(f"/evento/{criado['evento_id']}")

    def test_edicao_sem_os_campos_nao_apaga_o_que_estava_gravado(
        self, superadmin, evento_completo
    ):
        """Regressao do defeito da Sprint 4: o dado sumia sem aviso."""
        identificador = evento_completo["evento_id"]
        resposta = superadmin.put(
            f"/evento/{identificador}", json=_evento_online(nome="Congresso renomeado")
        )
        assert resposta.status_code == 200, resposta.text

        relido = superadmin.get(f"/evento/{identificador}").json()
        assert relido["nome"] == "Congresso renomeado"
        for campo, valor in CAMPOS_US02.items():
            assert relido[campo] == valor, campo

    def test_vagas_negativas_sao_recusadas(self, superadmin):
        resposta = superadmin.post("/evento/", json=_evento_online(vagas=-1))
        assert resposta.status_code == 422


# ------------------------------------------------------------------ US22


@pytest.fixture
def institucional_restaurado(superadmin):
    """
    Guarda o conteudo antes do teste e o devolve depois.

    Limite: se o banco estava sem conteudo, nao ha como voltar ao vazio — o
    PUT recusa corpo vazio de proposito (US22). Nesse caso fica o texto
    marcado abaixo. No CI o banco nasce vazio a cada execucao.
    """
    antes = superadmin.get("/institucional").json()
    yield
    if antes["missao"] or antes["visao"] or antes["valores"]:
        superadmin.put("/institucional", json=antes)


class TestMissaoVisaoValores:
    """US22 / RF25 — a tabela `institucional` so existe se a migration rodou."""

    def test_leitura_publica_responde_no_postgres(self, anonimo):
        """Um 500 aqui e migration nao aplicada."""
        resposta = anonimo.get("/institucional")

        assert resposta.status_code == 200, resposta.text
        assert set(resposta.json()) == {"missao", "visao", "valores"}
        assert isinstance(resposta.json()["valores"], list)

    def test_conteudo_salvo_volta_para_o_visitante(
        self, superadmin, anonimo, institucional_restaurado
    ):
        """`valores` e JSON no Postgres: a lista volta na mesma ordem."""
        corpo = {
            "missao": "Texto de teste de endpoint (pode ser substituido).",
            "visao": "Visao de teste de endpoint.",
            "valores": ["Fe", "Servico", "Comunhao"],
        }
        salvo = superadmin.put("/institucional", json=corpo)
        assert salvo.status_code == 200, salvo.text

        assert anonimo.get("/institucional").json() == corpo

    def test_corpo_vazio_e_recusado(self, superadmin):
        assert superadmin.put("/institucional", json={}).status_code == 422

    def test_visitante_nao_edita(self, anonimo):
        resposta = anonimo.put("/institucional", json={"missao": "Intruso"})
        assert resposta.status_code in (401, 403)

    def test_administrador_de_setor_nao_edita(self, admin_eventos, admin_produtos):
        for cliente in (admin_eventos, admin_produtos):
            resposta = cliente.put("/institucional", json={"missao": "Intruso"})
            assert resposta.status_code == 403


# ------------------------------------------------------------------ US21


@pytest.fixture
def produto(admin_produtos, superadmin):
    resposta = admin_produtos.post(
        "/produto/",
        json={
            "nome": "Camiseta de endpoint",
            "descricao": "Criado pelos testes de endpoint; pode ser apagado.",
        },
    )
    assert resposta.status_code == 201, resposta.text
    criado = resposta.json()
    yield criado
    superadmin.delete(f"/produto/{criado['produto_id']}")


class TestPedidosDeProduto:
    """US21 / RF57 — a tabela `pedido` e as rotas do setor de produtos."""

    def test_setor_de_produtos_lista_os_pedidos(self, admin_produtos):
        """CA1 — e a tabela da migration `a7f3c1d9e5b2` respondendo."""
        resposta = admin_produtos.get("/pedido/")

        assert resposta.status_code == 200, resposta.text
        assert isinstance(resposta.json(), list)

    def test_superadmin_lista_os_pedidos(self, superadmin):
        assert superadmin.get("/pedido/").status_code == 200

    def test_outro_setor_nao_lista(self, admin_eventos):
        # Um admin de OUTRO setor (eventos) e barrado em /pedido/.
        #
        # O admin SEM nenhum papel de setor NAO entra aqui de proposito: a
        # porta de retrocompatibilidade da US03 (verificar_permissao_setor em
        # src/security.py) o deixa alcancar todos os setores, e esse
        # comportamento e travado de proposito em
        # tests/unit/test_achados_exploratorios.py
        # ::test_admin_sem_papel_de_setor_ainda_alcanca_todos_os_setores.
        # Exigir 403 dele aqui contradiz aquele teste — os dois nao podem
        # ficar verdes ao mesmo tempo.
        assert admin_eventos.get("/pedido/").status_code == 403

    def test_visitante_nao_lista(self, anonimo):
        assert anonimo.get("/pedido/").status_code in (401, 403)

    def test_mudar_situacao_de_pedido_inexistente_responde_404(self, admin_produtos):
        resposta = admin_produtos.patch("/pedido/999999999/status", json={"status": "concluido"})
        assert resposta.status_code == 404

    def test_situacao_fora_da_lista_responde_422(self, admin_produtos):
        resposta = admin_produtos.patch("/pedido/1/status", json={"status": "comprado"})
        assert resposta.status_code == 422

    def test_outro_setor_nao_muda_situacao(self, admin_eventos):
        resposta = admin_eventos.patch("/pedido/1/status", json={"status": "concluido"})
        assert resposta.status_code == 403

    def test_link_do_formulario_de_pedido_e_gravado(self, admin_produtos, anonimo, produto):
        """A coluna `produto.formulario_pedido_link` veio da mesma migration."""
        link = "https://docs.google.com/forms/d/ID-DE-ENDPOINT/edit"
        identificador = produto["produto_id"]

        resposta = admin_produtos.put(
            f"/produto/{identificador}",
            json={"nome": produto["nome"], "formulario_pedido_link": link},
        )
        assert resposta.status_code == 200, resposta.text

        assert anonimo.get(f"/produto/{identificador}").json()["formulario_pedido_link"] == link

    def test_produto_novo_nasce_sem_formulario(self, produto):
        assert produto["formulario_pedido_link"] is None

    def test_sincronizar_produto_sem_formulario_responde_404(self, admin_produtos, produto):
        """Responde antes de falar com o Google."""
        resposta = admin_produtos.get(f"/formulario/produtos/{produto['produto_id']}/pedidos")
        assert resposta.status_code == 404

    def test_sincronizar_produto_inexistente_responde_404(self, admin_produtos):
        resposta = admin_produtos.get("/formulario/produtos/999999999/pedidos")
        assert resposta.status_code == 404

    def test_produto_sem_pedidos_continua_podendo_ser_excluido(self, admin_produtos, superadmin):
        """O 409 da US21 vale so para produto com pedidos."""
        criado = admin_produtos.post("/produto/", json={"nome": "Efemero de endpoint"}).json()

        assert superadmin.delete(f"/produto/{criado['produto_id']}").status_code == 204
