"""
Leitura de um formulario do Google: como achar o formulario e como achar as
perguntas dentro dele.

Esta logica vive fora do repositorio de proposito. Ela e pura — nao toca banco,
nao toca rede — e e exatamente a parte que falhava em silencio: quando o link
nao era reconhecido ou quando as perguntas tinham outro titulo, nenhuma resposta
era gravada e ninguem ficava sabendo por que.

Registrado na reuniao de validacao de 23/11/2026: a cliente preencheu um
formulario ao vivo e a inscricao nao apareceu em lista nenhuma.
"""

import re
import unicodedata

# Titulos aceitos para cada campo, em ordem de prioridade. A comparacao e feita
# sobre o titulo normalizado (sem acento, sem pontuacao, minusculo), entao
# "E-mail:", "e-mail" e "Email" caem todos em "e mail"/"email".
#
# A lista e fechada de proposito: casar por "contem" pegaria "Nome da igreja"
# no formulario de lideres, que e outro campo.
TITULOS_NOME = (
    "nome",
    "nome completo",
    "seu nome",
    "nome e sobrenome",
    "qual seu nome",
    "qual e o seu nome",
    "nome do participante",
    "nome do voluntario",
)

TITULOS_EMAIL = (
    "email",
    "e mail",
    "seu email",
    "seu e mail",
    "qual seu email",
    "qual e o seu email",
    "endereco de email",
    "email para contato",
    "e mail para contato",
)

_AJUDA_LINK = (
    "Abra o formulario no Google Forms em modo de edicao e cole aqui a URL da "
    "barra de enderecos, a que termina em /edit."
)


def normalizar_titulo(titulo: str) -> str:
    """Reduz um titulo de pergunta a sua forma comparavel.

    Tira acento, troca qualquer pontuacao por espaco e colapsa os espacos.
    "E-mail:" e "E‑mail *" viram "e mail"; "Nome  Completo" vira "nome completo".
    """
    if not titulo:
        return ""
    decomposto = unicodedata.normalize("NFKD", titulo)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    apenas_alfanumerico = re.sub(r"[^a-z0-9]+", " ", sem_acento.lower())
    return " ".join(apenas_alfanumerico.split())


def localizar_id_pergunta(
    mapa_perguntas: dict[str, str],
    titulos_aceitos: tuple[str, ...],
) -> str | None:
    """Id da primeira pergunta cujo titulo bate com um dos aceitos.

    `mapa_perguntas` e {id_da_pergunta: titulo}, como o Google devolve. A ordem
    de `titulos_aceitos` decide a prioridade: num formulario que tenha "Nome" e
    "Nome completo", "Nome" ganha por estar antes na lista.
    """
    por_titulo: dict[str, str] = {}
    for pergunta_id, titulo in mapa_perguntas.items():
        por_titulo.setdefault(normalizar_titulo(titulo), pergunta_id)

    for aceito in titulos_aceitos:
        if aceito in por_titulo:
            return por_titulo[aceito]
    return None


def extrair_formulario_id(link: str) -> str:
    """Id do formulario a partir do link, ou ValueError dizendo o que fazer.

    A API do Google Forms trabalha com o id que aparece no link de EDICAO
    (`/forms/d/<id>/edit`). O link de compartilhar (`/forms/d/e/<id>/viewform`)
    carrega outro identificador, que a API nao aceita, e o encurtado
    (`forms.gle/...`) nao carrega identificador nenhum.

    Antes de 23/11/2026 o link de compartilhar passava pela verificacao e o id
    extraido virava a letra "e" — a chamada ao Google falhava e a tela mostrava
    lista vazia, sem dizer nada. Agora cada formato errado tem a sua mensagem.
    """
    if not link or not link.strip():
        raise ValueError("Nao ha link de formulario configurado aqui.")

    texto = link.strip()

    # Precisa vir antes da busca pelo id: o link de compartilhar tambem contem
    # "/forms/d/", e era assim que o id virava "e".
    if "/forms/d/e/" in texto:
        raise ValueError(
            f"Esse e o link de compartilhar do Forms, que a API do Google nao "
            f"aceita. {_AJUDA_LINK}"
        )

    if "forms.gle/" in texto:
        raise ValueError(
            f"Esse e um link encurtado do Forms, que nao identifica o "
            f"formulario. {_AJUDA_LINK}"
        )

    encontrado = re.search(r"/forms/d/([A-Za-z0-9_-]+)", texto)
    if encontrado:
        return encontrado.group(1)

    raise ValueError(f"Nao reconheci esse link do Google Forms. {_AJUDA_LINK}")
