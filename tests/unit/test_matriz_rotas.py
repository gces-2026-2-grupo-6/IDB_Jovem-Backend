"""
Matriz de autorizacao lida da propria aplicacao.

A matriz da Sprint 1 era uma lista escrita a mao: testava verificar_roles com
os papeis listados, mas nao conferia se o controlador de fato usava aqueles
papeis. Uma rota nova, ou uma dependencia removida, passava sem aviso — foi
assim que GET /formulario/eventos/{id}/inscricoes ficou publica.

Aqui a exigencia de cada rota e extraida das dependencias registradas no
FastAPI e comparada com MATRIZ. Consequencias:

  - rota nova sem entrada na MATRIZ faz o teste falhar, obrigando a decidir
    e documentar quem pode acessa-la;
  - toda rota que nao seja GET precisa de guarda;
  - toda exclusao exige superadmin (regra definida pela cliente na elicitacao).

Ao alterar a MATRIZ, atualize docs/projeto/matriz-autorizacao.md no
repositorio de documentacao.
"""

import pytest
from fastapi.routing import APIRoute

from src.main import app

PUBLICA = None
SUPERADMIN = "papeis:superadmin"
ADMIN_OU_SUPERADMIN = "papeis:admin,superadmin"
SETOR_EVENTOS = "setor:eventos"
SETOR_PRODUTOS = "setor:produtos"
SETOR_INSCRICOES = "setor:inscricoes"

MATRIZ = {
    # Sistema
    ("GET", "/"): PUBLICA,
    ("GET", "/health"): PUBLICA,
    ("GET", "/auth/login"): PUBLICA,
    ("GET", "/auth/callback"): PUBLICA,
    # Administradores
    ("GET", "/admin/"): SUPERADMIN,
    ("GET", "/admin/{admin_id}"): SUPERADMIN,
    ("POST", "/admin/"): SUPERADMIN,
    ("DELETE", "/admin/{admin_id}"): SUPERADMIN,
    # Eventos
    ("GET", "/evento/"): PUBLICA,
    ("GET", "/evento/buscar"): PUBLICA,
    ("GET", "/evento/{evento_id}"): PUBLICA,
    ("GET", "/evento/{evento_id}/galeria"): PUBLICA,
    ("POST", "/evento/"): SETOR_EVENTOS,
    ("PUT", "/evento/{evento_id}"): SETOR_EVENTOS,
    ("DELETE", "/evento/{evento_id}"): SUPERADMIN,
    # Participantes do evento
    ("GET", "/evento/{evento_id}/participantes"): PUBLICA,
    ("POST", "/evento/{evento_id}/participantes/{participante_id}"): SETOR_EVENTOS,
    ("DELETE", "/evento/{evento_id}/participantes/{participante_id}"): SUPERADMIN,
    # Atividades (programacao)
    ("GET", "/evento/{evento_id}/atividade"): PUBLICA,
    ("GET", "/evento/atividade/{atividade_id}"): PUBLICA,
    ("POST", "/evento/{evento_id}/atividade"): SETOR_EVENTOS,
    ("PUT", "/evento/atividade/{atividade_id}"): SETOR_EVENTOS,
    ("DELETE", "/evento/atividade/{atividade_id}"): SUPERADMIN,
    # Bandas e palestrantes
    ("GET", "/banda-palestrante/"): PUBLICA,
    ("GET", "/banda-palestrante/{participante_id}"): PUBLICA,
    ("POST", "/banda-palestrante/"): SETOR_EVENTOS,
    ("PUT", "/banda-palestrante/{participante_id}"): SETOR_EVENTOS,
    ("DELETE", "/banda-palestrante/{participante_id}"): SUPERADMIN,
    # Produtos
    ("GET", "/produto/"): PUBLICA,
    ("GET", "/produto/{produto_id}"): PUBLICA,
    ("POST", "/produto/"): SETOR_PRODUTOS,
    ("PUT", "/produto/{produto_id}"): SETOR_PRODUTOS,
    ("DELETE", "/produto/{produto_id}"): SUPERADMIN,
    # Voluntarios e inscricoes
    ("GET", "/voluntarios/"): SETOR_INSCRICOES,
    ("GET", "/voluntarios/{voluntario_id}"): SETOR_INSCRICOES,
    ("GET", "/voluntarios/evento/{evento_id}"): SETOR_INSCRICOES,
    ("GET", "/voluntarios/evento/{evento_id}/contagem"): SETOR_INSCRICOES,
    ("POST", "/voluntarios/"): SETOR_INSCRICOES,
    ("PATCH", "/voluntarios/{voluntario_id}/evento/{evento_id}/status"): SETOR_INSCRICOES,
    ("DELETE", "/voluntarios/{voluntario_id}"): SUPERADMIN,
    ("GET", "/formulario/eventos/{evento_id}/inscricoes"): SETOR_INSCRICOES,
    # Lideres
    ("GET", "/lider/"): PUBLICA,
    ("GET", "/lider/{lider_id}"): PUBLICA,
    ("POST", "/lider/"): ADMIN_OU_SUPERADMIN,
    ("PUT", "/lider/{lider_id}"): ADMIN_OU_SUPERADMIN,
    ("DELETE", "/lider/{lider_id}"): SUPERADMIN,
    # Midia e mapa
    ("GET", "/galeria/fotos"): ADMIN_OU_SUPERADMIN,
    ("GET", "/drive/imagem/{file_id}"): PUBLICA,
    ("GET", "/mapa/endereco"): PUBLICA,
}


def _coletar_exigencias(dependente, encontradas):
    """Percorre a arvore de dependencias e anota as guardas de src/security.py."""
    chamada = dependente.call
    codigo = getattr(chamada, "__code__", None)
    fechamento = getattr(chamada, "__closure__", None)
    if codigo is not None and fechamento and codigo.co_freevars:
        celulas = dict(zip(codigo.co_freevars, (c.cell_contents for c in fechamento)))
        if "roles_exigidas" in celulas:
            encontradas.append("papeis:" + ",".join(sorted(celulas["roles_exigidas"])))
        if "setor_alvo" in celulas:
            encontradas.append("setor:" + celulas["setor_alvo"])
    for sub in dependente.dependencies:
        _coletar_exigencias(sub, encontradas)


def exigencia_da_rota(rota: APIRoute):
    encontradas = []
    # rota.dependant ja inclui as dependencias do decorador e do include_router.
    _coletar_exigencias(rota.dependant, encontradas)
    if not encontradas:
        return PUBLICA
    assert len(set(encontradas)) == 1, (
        f"{rota.path} acumula guardas diferentes: {encontradas}. "
        "Mantenha uma unica exigencia por rota para que a matriz seja legivel."
    )
    return encontradas[0]


def rotas_da_aplicacao():
    return {
        (metodo, rota.path): exigencia_da_rota(rota)
        for rota in app.routes
        if isinstance(rota, APIRoute)
        for metodo in rota.methods
    }


ROTAS = rotas_da_aplicacao()


def test_matriz_cobre_exatamente_as_rotas_da_aplicacao():
    sem_entrada = sorted(set(ROTAS) - set(MATRIZ))
    inexistentes = sorted(set(MATRIZ) - set(ROTAS))
    assert not sem_entrada, (
        f"Rotas sem decisao de acesso na MATRIZ: {sem_entrada}. "
        "Decida quem pode acessa-las e registre aqui e na documentacao."
    )
    assert not inexistentes, f"Entradas da MATRIZ sem rota correspondente: {inexistentes}."


@pytest.mark.parametrize(
    "metodo,caminho",
    sorted(MATRIZ),
    ids=[f"{m} {p}" for m, p in sorted(MATRIZ)],
)
def test_rota_exige_o_que_a_matriz_define(metodo, caminho):
    if (metodo, caminho) not in ROTAS:
        pytest.skip("Rota inexistente — apontada no teste de cobertura da matriz.")
    assert ROTAS[(metodo, caminho)] == MATRIZ[(metodo, caminho)]


def test_toda_rota_de_escrita_tem_guarda():
    desprotegidas = sorted(
        chave for chave, exigencia in ROTAS.items()
        if chave[0] != "GET" and exigencia is PUBLICA
    )
    assert not desprotegidas, f"Rotas de escrita sem verificacao de papel: {desprotegidas}"


def test_toda_exclusao_exige_superadmin():
    """A cliente definiu que so o superadministrador exclui conteudo."""
    divergentes = sorted(
        chave for chave, exigencia in ROTAS.items()
        if chave[0] == "DELETE" and exigencia != SUPERADMIN
    )
    assert not divergentes, f"Exclusoes que nao exigem superadmin: {divergentes}"
