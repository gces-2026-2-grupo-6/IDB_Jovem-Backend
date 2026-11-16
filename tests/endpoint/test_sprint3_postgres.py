"""
As historias da Sprint 3, gravando e relendo no Postgres de verdade.

A licao da QA22 era: a suite unitaria roda em SQLite, a producao em Postgres,
e o que so existe no Postgres aparece como coberto sem nunca ter sido
executado. Ela foi aplicada a busca por trigrama — e a mais nada. As sete
historias que os trios entregaram na Sprint 3 chegaram com colunas e modulos
novos, e ate aqui nenhum teste as exercitava contra o banco de producao:
`tests/endpoint/` cobria so a busca e a saude do container.

O que este modulo exercita e so existe de verdade no Postgres:

- `nova_data`, `data_inicio` e `data_fim` sao `DateTime(timezone=True)` —
  `timestamptz`. SQLite guarda texto; o que entra com fuso de Brasilia tem
  que sair no mesmo instante (RNF08);
- `datas` e `ARRAY(Date)`, tipo que o SQLite nem tem;
- as tabelas `material` e `painel` vieram de migracao nova, e a aplicacao em
  container so as enxerga se a migracao rodou — o que nenhum teste conferia;
- os valores padrao de `situacao` e `modalidade` sao `server_default`: quem
  decide e o banco.

Os testes criam os proprios dados pela API, como superadministradora, e
apagam o que criaram. Os eventos sao sempre online: evento presencial consulta
um servico externo de enderecos na criacao, e teste de endpoint nao pode
depender da internet para passar.

Os tokens vem do emissor de teste descrito em `conftest.py`.
"""

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.endpoint

BRASILIA = timezone(timedelta(hours=-3))


def _instante(texto: str) -> datetime:
    """Le a data devolvida pela API como instante, com fuso.

    A comparacao e por instante, nunca por texto: o Postgres devolve
    `timestamptz` no fuso da sessao, entao o mesmo momento volta como
    `19:00-03:00` numa maquina e `22:00+00:00` em outra. As duas respostas
    estao certas; o que nao pode e voltar sem fuso.
    """
    lido = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    assert lido.tzinfo is not None, f"data devolvida sem fuso: {texto!r}"
    return lido


def _evento_online(**extras) -> dict:
    inicio = datetime(2027, 5, 1, 19, 0, tzinfo=BRASILIA)
    corpo = {
        "nome": "Conferencia de endpoint",
        "tipo_evento": "Conferência",
        "descricao": "Criado pelos testes de endpoint; pode ser apagado.",
        "modalidade": "online",
        "link_transmissao": "https://exemplo.invalid/ao-vivo",
        "data_inicio": inicio.isoformat(),
        "data_fim": (inicio + timedelta(hours=2)).isoformat(),
    }
    corpo.update(extras)
    return corpo


@pytest.fixture
def evento(superadmin):
    """Um evento online gravado no Postgres, apagado ao fim do teste."""
    resposta = superadmin.post("/evento/", json=_evento_online())
    assert resposta.status_code == 201, resposta.text
    criado = resposta.json()
    yield criado
    superadmin.delete(f"/evento/{criado['evento_id']}")


# ------------------------------------------------------------------ US14


class TestSituacaoDoEvento:
    """US14 / RF12 — cancelar e adiar, gravado em `timestamptz`."""

    def test_evento_nasce_ativo_e_sem_nova_data(self, evento):
        assert evento["situacao"] == "ativo"
        assert evento["nova_data"] is None

    def test_adiar_preserva_o_instante_da_nova_data(self, superadmin, evento):
        """A nova data entra com fuso de Brasilia e tem que sair no mesmo instante.

        E o teste que o SQLite nao consegue fazer: la a coluna guarda o texto
        como veio. No Postgres o valor e convertido para UTC na gravacao e
        devolvido no fuso da sessao — se algum ponto do caminho perder o fuso,
        o evento adiado aparece tres horas fora do lugar para o visitante.
        """
        nova = datetime(2027, 6, 10, 19, 0, tzinfo=BRASILIA)
        resposta = superadmin.patch(
            f"/evento/{evento['evento_id']}/situacao",
            json={"situacao": "adiado", "nova_data": nova.isoformat()},
        )
        assert resposta.status_code == 200, resposta.text

        relido = superadmin.get(f"/evento/{evento['evento_id']}").json()
        assert relido["situacao"] == "adiado"
        assert _instante(relido["nova_data"]) == nova

    def test_cancelar_descarta_a_nova_data(self, superadmin, evento):
        """`nova_data` so vale no adiado; no cancelado o servidor zera."""
        identificador = evento["evento_id"]
        superadmin.patch(
            f"/evento/{identificador}/situacao",
            json={"situacao": "adiado", "nova_data": "2027-06-10T19:00:00-03:00"},
        )
        resposta = superadmin.patch(
            f"/evento/{identificador}/situacao",
            json={"situacao": "cancelado", "nova_data": "2027-06-10T19:00:00-03:00"},
        )
        assert resposta.status_code == 200, resposta.text

        relido = superadmin.get(f"/evento/{identificador}").json()
        assert relido["situacao"] == "cancelado"
        assert relido["nova_data"] is None

    def test_voltar_para_ativo_desfaz_a_marcacao(self, superadmin, evento):
        identificador = evento["evento_id"]
        superadmin.patch(f"/evento/{identificador}/situacao", json={"situacao": "cancelado"})
        resposta = superadmin.patch(
            f"/evento/{identificador}/situacao", json={"situacao": "ativo"}
        )
        assert resposta.status_code == 200, resposta.text
        assert superadmin.get(f"/evento/{identificador}").json()["situacao"] == "ativo"

    def test_marcar_nao_apaga_o_evento_nem_as_datas(self, superadmin, evento):
        """CA3 — marcar e uma anotacao: as datas originais ficam como estavam."""
        identificador = evento["evento_id"]
        superadmin.patch(f"/evento/{identificador}/situacao", json={"situacao": "cancelado"})

        relido = superadmin.get(f"/evento/{identificador}").json()
        assert _instante(relido["data_inicio"]) == _instante(evento["data_inicio"])
        assert _instante(relido["data_fim"]) == _instante(evento["data_fim"])

    def test_listagem_publica_expoe_a_situacao(self, superadmin, anonimo, evento):
        """CA4 — o visitante precisa receber a marcacao, sem login."""
        identificador = evento["evento_id"]
        superadmin.patch(f"/evento/{identificador}/situacao", json={"situacao": "cancelado"})

        listagem = anonimo.get("/evento/")
        assert listagem.status_code == 200, listagem.text
        marcados = {e["evento_id"]: e["situacao"] for e in listagem.json()}
        assert marcados.get(identificador) == "cancelado"

    def test_situacao_desconhecida_e_recusada(self, superadmin, evento):
        resposta = superadmin.patch(
            f"/evento/{evento['evento_id']}/situacao", json={"situacao": "suspenso"}
        )
        assert resposta.status_code == 422

    def test_marcar_exige_autenticacao(self, anonimo, evento):
        resposta = anonimo.patch(
            f"/evento/{evento['evento_id']}/situacao", json={"situacao": "cancelado"}
        )
        assert resposta.status_code in (401, 403)

    def test_evento_inexistente_devolve_404(self, superadmin):
        resposta = superadmin.patch("/evento/999999999/situacao", json={"situacao": "cancelado"})
        assert resposta.status_code == 404


# ------------------------------------------------------- datas e modalidade


class TestDatasEModalidadeNoPostgres:
    """US01, US19 e RNF08 — os tipos que so existem no banco de producao."""

    def test_inicio_e_fim_voltam_no_mesmo_instante(self, evento):
        """`timestamptz` de ponta a ponta: entra 19h de Brasilia, sai o mesmo instante."""
        esperado = datetime(2027, 5, 1, 19, 0, tzinfo=BRASILIA)
        assert _instante(evento["data_inicio"]) == esperado
        assert _instante(evento["data_fim"]) == esperado + timedelta(hours=2)

    def test_evento_de_varios_dias_guarda_a_lista_de_datas(self, superadmin):
        """US01 — `datas` e `ARRAY(Date)`, tipo que o SQLite nao tem.

        A lista atravessa a virada de mes de proposito: e o caso que ja deu
        defeito na tela, e aqui se confere que o banco devolve os dias na
        ordem e sem deslocamento de fuso (data pura nao tem hora para deslocar).
        """
        inicio = datetime(2027, 1, 30, 9, 0, tzinfo=BRASILIA)
        dias = ["2027-01-30", "2027-01-31", "2027-02-01"]
        resposta = superadmin.post(
            "/evento/",
            json=_evento_online(
                nome="Acampamento de endpoint na virada do mes",
                tipo_evento="Acampamento",
                data_inicio=inicio.isoformat(),
                data_fim=(inicio + timedelta(days=2, hours=8)).isoformat(),
                datas=dias,
            ),
        )
        assert resposta.status_code == 201, resposta.text
        identificador = resposta.json()["evento_id"]
        try:
            relido = superadmin.get(f"/evento/{identificador}").json()
            assert relido["datas"] == dias
        finally:
            superadmin.delete(f"/evento/{identificador}")

    def test_evento_online_guarda_o_link_e_nenhum_endereco(self, evento):
        """US19, CA5 — o online guarda o link no lugar do endereco."""
        assert evento["modalidade"] == "online"
        assert evento["link_transmissao"] == "https://exemplo.invalid/ao-vivo"
        assert evento["local_latitude"] is None
        assert evento["local_longitude"] is None
        assert evento["nome_local"] is None

    def test_coordenadas_enviadas_num_evento_online_sao_descartadas(self, superadmin):
        """O servidor decide pelo que a modalidade diz, nao pelo que veio no corpo."""
        resposta = superadmin.post(
            "/evento/",
            json=_evento_online(local_latitude=-15.7939, local_longitude=-47.8828),
        )
        assert resposta.status_code == 201, resposta.text
        criado = resposta.json()
        try:
            assert criado["local_latitude"] is None
            assert criado["local_longitude"] is None
        finally:
            superadmin.delete(f"/evento/{criado['evento_id']}")

    def test_evento_presencial_sem_coordenadas_e_recusado(self, superadmin):
        corpo = _evento_online(modalidade="presencial")
        corpo.pop("link_transmissao")
        resposta = superadmin.post("/evento/", json=corpo)
        assert resposta.status_code == 422

    def test_fim_antes_do_inicio_e_recusado(self, superadmin):
        inicio = datetime(2027, 5, 1, 19, 0, tzinfo=BRASILIA)
        resposta = superadmin.post(
            "/evento/",
            json=_evento_online(
                data_inicio=inicio.isoformat(),
                data_fim=(inicio - timedelta(hours=1)).isoformat(),
            ),
        )
        assert resposta.status_code in (400, 422)


# ------------------------------------------------------------------ US11


@pytest.fixture
def material(superadmin):
    resposta = superadmin.post(
        "/material/",
        json={
            "titulo": "Manual de endpoint",
            "descricao": "Criado pelos testes de endpoint; pode ser apagado.",
            "tipo": "documento",
            "link": "https://exemplo.invalid/manual.pdf",
        },
    )
    assert resposta.status_code == 201, resposta.text
    criado = resposta.json()
    yield criado
    superadmin.delete(f"/material/{criado['material_id']}")


class TestMateriais:
    """US11 / RF54 — a tabela `material` so existe se a migracao rodou."""

    def test_listagem_publica_responde_no_postgres(self, anonimo):
        """O caso que importa: a tabela existe no banco em que a aplicacao roda.

        Um 500 aqui significa migracao nao aplicada — exatamente o deploy com
        `git pull` e `build` mas sem `alembic upgrade head`.
        """
        resposta = anonimo.get("/material/")
        assert resposta.status_code == 200, resposta.text
        assert isinstance(resposta.json(), list)

    def test_material_criado_aparece_para_o_visitante(self, anonimo, material):
        listagem = anonimo.get("/material/").json()
        assert material["material_id"] in {m["material_id"] for m in listagem}

        unico = anonimo.get(f"/material/{material['material_id']}")
        assert unico.status_code == 200
        assert unico.json()["titulo"] == "Manual de endpoint"

    def test_material_traz_link_de_download_e_data_de_criacao(self, material):
        """`criado_em` vem do banco, nao da aplicacao — so o Postgres responde."""
        assert material["url_download"], "material sem link de download"
        assert material["criado_em"], "material sem data de criacao"

    def test_arquivo_do_drive_baixa_pela_rota_do_backend(self, superadmin):
        """O achado da Sprint 3: exibir nao e baixar.

        Link de arquivo do Drive abre a pre-visualizacao; o botao "Baixar"
        precisa apontar para a rota de download do backend.
        """
        resposta = superadmin.post(
            "/material/",
            json={
                "titulo": "Foto de endpoint",
                "tipo": "foto",
                "link": "https://drive.google.com/file/d/ID-DE-ENDPOINT-123/view",
            },
        )
        assert resposta.status_code == 201, resposta.text
        criado = resposta.json()
        try:
            assert "/drive/download/ID-DE-ENDPOINT-123" in criado["url_download"]
        finally:
            superadmin.delete(f"/material/{criado['material_id']}")

    def test_edicao_e_gravada(self, superadmin, material):
        identificador = material["material_id"]
        resposta = superadmin.put(
            f"/material/{identificador}",
            json={
                "titulo": "Manual de endpoint, segunda edicao",
                "tipo": "documento",
                "link": "https://exemplo.invalid/manual-v2.pdf",
            },
        )
        assert resposta.status_code == 200, resposta.text
        relido = superadmin.get(f"/material/{identificador}").json()
        assert relido["titulo"] == "Manual de endpoint, segunda edicao"
        assert relido["link"] == "https://exemplo.invalid/manual-v2.pdf"

    def test_material_apagado_some_da_listagem(self, superadmin, anonimo):
        criado = superadmin.post(
            "/material/",
            json={"titulo": "Efemero", "tipo": "video", "link": "https://exemplo.invalid/v"},
        ).json()
        identificador = criado["material_id"]

        assert superadmin.delete(f"/material/{identificador}").status_code == 204
        assert anonimo.get(f"/material/{identificador}").status_code == 404

    def test_link_sem_http_e_recusado(self, superadmin):
        resposta = superadmin.post(
            "/material/",
            json={"titulo": "Link torto", "tipo": "documento", "link": "drive.google.com/x"},
        )
        assert resposta.status_code == 422

    def test_tipo_desconhecido_e_recusado(self, superadmin):
        resposta = superadmin.post(
            "/material/",
            json={"titulo": "Tipo torto", "tipo": "planilha", "link": "https://exemplo.invalid/x"},
        )
        assert resposta.status_code == 422

    def test_visitante_nao_cadastra_material(self, anonimo):
        resposta = anonimo.post(
            "/material/",
            json={"titulo": "Intruso", "tipo": "documento", "link": "https://exemplo.invalid/x"},
        )
        assert resposta.status_code in (401, 403)

    def test_administrador_comum_nao_cadastra_material(self, admin_sem_setor):
        """CA — o painel de materiais e restrito a superadministradora."""
        resposta = admin_sem_setor.post(
            "/material/",
            json={"titulo": "Intruso", "tipo": "documento", "link": "https://exemplo.invalid/x"},
        )
        assert resposta.status_code == 403


# ------------------------------------------------------------------ US10


@pytest.fixture
def links_do_painel_restaurados(superadmin):
    """Guarda os links fixados antes do teste e os devolve depois."""
    antes = superadmin.get("/painel/links").json()
    yield
    superadmin.put(
        "/painel/links",
        json={
            "link_cadastro_lideres": antes.get("link_cadastro_lideres") or "",
            "link_planilha_lideres": antes.get("link_planilha_lideres") or "",
        },
    )


class TestLinksDoPainel:
    """US10 / RF58 — links fixados no painel da superadministradora."""

    def test_links_gravados_voltam_na_leitura(self, superadmin, links_do_painel_restaurados):
        resposta = superadmin.put(
            "/painel/links",
            json={
                "link_cadastro_lideres": "https://exemplo.invalid/cadastro",
                "link_planilha_lideres": "https://exemplo.invalid/planilha",
            },
        )
        assert resposta.status_code == 200, resposta.text

        lido = superadmin.get("/painel/links").json()
        assert lido["link_cadastro_lideres"] == "https://exemplo.invalid/cadastro"
        assert lido["link_planilha_lideres"] == "https://exemplo.invalid/planilha"

    def test_atualizacao_parcial_nao_apaga_o_outro_link(
        self, superadmin, links_do_painel_restaurados
    ):
        """So o campo enviado muda — o contrato da atualizacao parcial."""
        superadmin.put(
            "/painel/links",
            json={
                "link_cadastro_lideres": "https://exemplo.invalid/cadastro",
                "link_planilha_lideres": "https://exemplo.invalid/planilha",
            },
        )
        superadmin.put(
            "/painel/links", json={"link_cadastro_lideres": "https://exemplo.invalid/novo"}
        )

        lido = superadmin.get("/painel/links").json()
        assert lido["link_cadastro_lideres"] == "https://exemplo.invalid/novo"
        assert lido["link_planilha_lideres"] == "https://exemplo.invalid/planilha"

    def test_texto_vazio_remove_o_link(self, superadmin, links_do_painel_restaurados):
        superadmin.put(
            "/painel/links", json={"link_cadastro_lideres": "https://exemplo.invalid/cadastro"}
        )
        superadmin.put("/painel/links", json={"link_cadastro_lideres": ""})
        assert superadmin.get("/painel/links").json()["link_cadastro_lideres"] is None

    def test_link_sem_http_e_recusado(self, superadmin):
        resposta = superadmin.put(
            "/painel/links", json={"link_cadastro_lideres": "forms.gle/abc"}
        )
        assert resposta.status_code == 422

    def test_visitante_nao_le_os_links(self, anonimo):
        assert anonimo.get("/painel/links").status_code in (401, 403)

    def test_administrador_de_setor_nao_le_os_links(self, admin_sem_setor):
        """CA4 — os links sao invisiveis para quem nao e superadministradora."""
        assert admin_sem_setor.get("/painel/links").status_code == 403
