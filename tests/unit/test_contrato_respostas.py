"""
Contrato das respostas publicadas pela API.

O front-end le campo por campo: `evento.local_latitude`, `lider.gestao`,
`item.image`. Renomear ou remover um campo nao quebra nenhum teste do back —
quebra a tela, em producao, sem aviso. Foi assim que o campo de coordenadas
derrubou a listagem publica: o contrato mudou de fato (de obrigatorio para
nulo) sem ninguem registrar.

Este arquivo fixa, para cada resposta que o front consome, **quais campos
existem** e **quais sao obrigatorios**. Mudar o contrato continua permitido —
so nao em silencio: a mudanca passa a exigir que alguem atualize esta lista, o
que coloca a decisao na revisao da PR.

Quando um campo novo entrar (modalidade do evento na US19, por exemplo), o
teste falha pedindo para acrescenta-lo aqui.
"""

import pytest

from src.main import app

# Campo listado aqui = campo que o front pode ler. Obrigatorio = o front pode
# contar com ele sempre presente, sem checagem de nulo.
CONTRATO = {
    "RespostaEvento": {
        "campos": {
            "calendario_evento_id", "data_fim", "data_inicio", "datas", "descricao",
            "evento_id", "formulario_link", "formulario_participante_link",
            "link_galeria", "link_imagem", "local_latitude", "local_longitude",
            "nome", "nome_local", "tipo_evento",
        },
        "obrigatorios": {"data_fim", "data_inicio", "evento_id", "nome"},
    },
    "RespostaLider": {
        "campos": {
            "cargo", "gestao", "imagem_url", "is_antigo", "lider_id",
            "mini_biografia", "nome", "ordem", "redes_sociais", "regiao",
        },
        "obrigatorios": {"cargo", "lider_id", "nome"},
    },
    "RespostaProduto": {
        "campos": {"descricao", "link_imagem", "link_produto", "nome", "produto_id"},
        "obrigatorios": {"nome", "produto_id"},
    },
    "RespostaBandaPalestrante": {
        "campos": {"link_foto", "nome", "participante_id", "profissao"},
        "obrigatorios": {"nome", "participante_id"},
    },
    "RespostaAtividade": {
        "campos": {
            "atividade_id", "descricao", "evento_id", "horario_inicio",
            "horario_termino", "nome",
        },
        "obrigatorios": {
            "atividade_id", "evento_id", "horario_inicio", "horario_termino", "nome",
        },
    },
    "RespostaInscricaoParticipante": {
        "campos": {
            "email", "evento_id", "link_resposta", "nome", "participante_id",
            "resposta_id",
        },
        "obrigatorios": {
            "email", "evento_id", "link_resposta", "nome", "participante_id",
            "resposta_id",
        },
    },
    "RespostaVoluntario": {
        "campos": {"email", "nome", "voluntario_id"},
        "obrigatorios": {"email", "nome", "voluntario_id"},
    },
    "RespostaItemGaleria": {
        "campos": {"event", "id", "image", "location", "url_download"},
        "obrigatorios": {"event", "id", "image", "location"},
    },
}

ESQUEMAS = app.openapi()["components"]["schemas"]


@pytest.mark.parametrize("nome", sorted(CONTRATO))
def test_resposta_existe_no_openapi(nome):
    assert nome in ESQUEMAS, (
        f"{nome} sumiu do contrato publicado. Se foi renomeada, atualize o CONTRATO "
        "e avise quem mantem o front-end."
    )


@pytest.mark.parametrize("nome", sorted(CONTRATO))
def test_campos_publicados_nao_mudaram(nome):
    atuais = set(ESQUEMAS[nome].get("properties", {}))
    esperados = CONTRATO[nome]["campos"]
    sumiram = esperados - atuais
    novos = atuais - esperados
    assert not sumiram, (
        f"{nome} deixou de publicar {sorted(sumiram)}. O front le esses campos: "
        "confirme que ninguem depende deles antes de atualizar o CONTRATO."
    )
    assert not novos, (
        f"{nome} passou a publicar {sorted(novos)}. Acrescente ao CONTRATO para "
        "registrar que o campo e publico e passa a ser mantido."
    )


@pytest.mark.parametrize("nome", sorted(CONTRATO))
def test_campos_obrigatorios_nao_mudaram(nome):
    atuais = set(ESQUEMAS[nome].get("required", []))
    esperados = CONTRATO[nome]["obrigatorios"]
    assert atuais == esperados, (
        f"{nome} mudou quais campos sempre vem preenchidos: antes {sorted(esperados)}, "
        f"agora {sorted(atuais)}. Campo que deixa de ser obrigatorio exige checagem de "
        "nulo no front; campo que passa a ser obrigatorio quebra registro antigo."
    )


def test_toda_rota_publicada_declara_uma_resposta():
    """
    Rota sem `response_model` devolve o que a camada de servico retornar, e o
    contrato deixa de existir para ela.
    """
    sem_contrato = []
    for caminho, metodos in app.openapi()["paths"].items():
        for metodo, operacao in metodos.items():
            ok = operacao.get("responses", {}).get("200") or operacao.get("responses", {}).get("201")
            if ok and "content" not in ok:
                sem_contrato.append(f"{metodo.upper()} {caminho}")
    assert not sem_contrato, f"Rotas sem contrato de resposta declarado: {sem_contrato}"
