import re
from urllib.parse import urlparse, parse_qs

from src.config import configuracoes

# IDs de arquivo do Google Drive sao compostos por letras, numeros, '_' e '-'.
_CLASSE_ID = r"[a-zA-Z0-9_-]"
_REGEX_FILE_D = re.compile(rf"/file/d/({_CLASSE_ID}+)")
_REGEX_D = re.compile(rf"/d/({_CLASSE_ID}+)")
_REGEX_ID_NU = re.compile(rf"^{_CLASSE_ID}{{10,}}$")


def extrair_file_id(link: str | None) -> str | None:
    """
    Extrai o file_id de um link do Google Drive em formatos comuns:
      - https://drive.google.com/file/d/{id}/view
      - https://drive.google.com/thumbnail?id={id}&sz=w1000
      - https://drive.google.com/uc?id={id}
      - https://drive.google.com/open?id={id}
      - https://lh3.googleusercontent.com/d/{id}
      - o proprio file_id "cru"
    Retorna None se nao for possivel identificar um file_id.
    """
    if not link:
        return None

    link = link.strip()

    # Já é um file_id "cru" (sem barra nem esquema).
    if _REGEX_ID_NU.fullmatch(link):
        return link

    correspondencia = _REGEX_FILE_D.search(link) or _REGEX_D.search(link)
    if correspondencia:
        return correspondencia.group(1)

    parametros = parse_qs(urlparse(link).query)
    if parametros.get("id"):
        return parametros["id"][0]

    return None


def montar_url_proxy(file_id: str) -> str:
    """Monta a URL absoluta do proxy de imagem deste backend para um file_id."""
    base = configuracoes.BASE_URL.rstrip("/")
    return f"{base}/drive/imagem/{file_id}"


def converter_link_para_proxy(link: str | None) -> str | None:
    """
    Converte um link de imagem do Drive na URL do proxy do backend.
    Se o link nao for do Drive (ou estiver vazio), devolve o valor original
    inalterado, preservando URLs externas.
    """
    file_id = extrair_file_id(link)
    if not file_id:
        return link
    return montar_url_proxy(file_id)


_HOSTS_DO_GOOGLE = ("drive.google.com", "docs.google.com", "googleusercontent.com")


def montar_url_download(file_id: str) -> str:
    """URL absoluta da rota de download deste backend para um file_id (US11)."""
    base = configuracoes.BASE_URL.rstrip("/")
    return f"{base}/drive/download/{file_id}"


def extrair_file_id_do_google(link: str | None) -> str | None:
    """
    Igual a extrair_file_id, mas só aceita links do Google ou o id cru.
    Evita tratar como arquivo do Drive um link qualquer que tenha "/d/" no
    caminho ou "?id=" na query.
    """
    if not link:
        return None
    link = link.strip()
    if _REGEX_ID_NU.fullmatch(link):
        return link
    host = urlparse(link).netloc.lower()
    if not any(host == dominio or host.endswith("." + dominio) for dominio in _HOSTS_DO_GOOGLE):
        return None
    return extrair_file_id(link)


def link_de_download(link: str | None) -> str | None:
    """
    Link que o front usa no botão "Baixar". Arquivo do Drive passa pela rota
    de download do backend, que devolve o arquivo com o nome original. Link
    externo (YouTube, site) é devolvido como está.
    """
    file_id = extrair_file_id_do_google(link)
    if not file_id:
        return link
    return montar_url_download(file_id)
