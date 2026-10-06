import os
import json
import base64
from typing import Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.drive.schema import RespostaDrive
from src.drive.model import ImagemCache
from src.drive.utils import montar_url_proxy
from src.auth.service import ServicoAuth

# Cache em memoria: { id_pasta: (timestamp, fotos) }
_CACHE_GALERIAS: dict[str, tuple[float, list[RespostaDrive]]] = {}

class ServicoDrive:

    def __init__(self):
        self.refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
        self.servico_auth = ServicoAuth()

    def _obter_token_valido(self) -> str:
        """Busca o refresh_token do .env, renova no Google e retorna o access_token ativo."""
        if not self.refresh_token:
            raise RuntimeError("GOOGLE_REFRESH_TOKEN nao configurado no arquivo .env")
        try:
            credenciais = self.servico_auth.obter_credenciais_validas(self.refresh_token)
            return credenciais.token
        except Exception as erro:
            raise RuntimeError("Falha automatica ao renovar credenciais do Google para o Drive") from erro

    @staticmethod
    def _escapar_valor_consulta(valor: str) -> str:
        """Escapa barra invertida e aspa simples para uso seguro na query da Drive API."""
        return valor.replace("\\", "\\\\").replace("'", "\\'")

    def _montar_url_busca_pasta(self, nome_pasta: str) -> str:
        nome_pasta = self._escapar_valor_consulta(nome_pasta)
        consulta = (
            "mimeType='application/vnd.google-apps.folder' "
            f"and name='{nome_pasta}' and trashed=false"
        )

        parametros = {
            "q": consulta,
            "fields": "files(id,name)",
            "pageSize": 1,
        }

        return f"https://www.googleapis.com/drive/v3/files?{urlencode(parametros)}"

    def _montar_url_busca_fotos(self, id_pasta: str) -> str:
        consulta = (
            f"'{id_pasta}' in parents "
            "and mimeType contains 'image/' "
            "and trashed=false"
        )

        parametros = {
            "q": consulta,
            "fields": "nextPageToken, files(id,name,mimeType)",
            "pageSize": 100,
        }

        return f"https://www.googleapis.com/drive/v3/files?{urlencode(parametros)}"

    def _montar_url_visualizacao(self, id_arquivo: str) -> str:
        return montar_url_proxy(id_arquivo)

    def _buscar_pasta_id(self, token: str, nome_pasta: str) -> str | None:

        url = self._montar_url_busca_pasta(nome_pasta)

        requisicao = Request(url)
        requisicao.add_header("Authorization", f"Bearer {token}")
        requisicao.add_header("Accept", "application/json")

        try:
            with urlopen(requisicao, timeout=10) as resposta:
                corpo = resposta.read().decode("utf-8")

        except (HTTPError, URLError) as erro:
            raise RuntimeError(
                "Falha ao buscar pasta no Google Drive"
            ) from erro

        dados = json.loads(corpo)
        arquivos = dados.get("files", [])

        if not arquivos:
            return None

        return arquivos[0].get("id")

    def _buscar_fotos_drive(
        self,
        token: str,
        id_pasta: str
    ) -> list[RespostaDrive]:
        import time

        # Configuracao do Cache (30 minutos)
        agora = time.time()
        if id_pasta in _CACHE_GALERIAS:
            tempo_salvo, fotos_salvas = _CACHE_GALERIAS[id_pasta]
            if agora - tempo_salvo < 1800:
                return fotos_salvas

        url_base = self._montar_url_busca_fotos(id_pasta)
        url_busca = url_base
        fotos = []

        while url_busca:
            requisicao = Request(url_busca)
            requisicao.add_header("Authorization", f"Bearer {token}")
            requisicao.add_header("Accept", "application/json")

            try:
                with urlopen(requisicao, timeout=10) as resposta:
                    corpo = resposta.read().decode("utf-8")

            except (HTTPError, URLError) as erro:
                raise RuntimeError(
                    "Falha ao buscar fotos no Google Drive"
                ) from erro

            dados = json.loads(corpo)
            arquivos = dados.get("files", [])

            for arquivo in arquivos:
                id_arquivo = arquivo.get("id")

                if not id_arquivo:
                    continue

                fotos.append(
                    RespostaDrive(
                        id=id_arquivo,
                        nome=arquivo.get("name", ""),
                        url_visualizacao=(
                            self._montar_url_visualizacao(id_arquivo)
                        ),
                    )
                )

            next_token = dados.get("nextPageToken")
            if next_token:
                url_busca = f"{url_base}&pageToken={next_token}"
            else:
                url_busca = None

        _CACHE_GALERIAS[id_pasta] = (agora, fotos)
        return fotos

    @staticmethod
    def limpar_cache():
        """Limpa o cache em memória das galerias do Drive."""
        _CACHE_GALERIAS.clear()

    @staticmethod
    def _extrair_id_pasta(valor: str) -> str | None:
        """
        Extrai o ID da pasta do Google Drive a partir de uma URL ou do proprio ID.
        Suporta formatos:
        - https://drive.google.com/drive/folders/1a2b3c4d5e...
        - https://drive.google.com/drive/u/0/folders/1a2b3c4d5e...
        - ID alfanumerico direto (ex.: 1a2b3c4d5e...)
        """
        import re
        valor = (valor or "").strip()
        match_url = re.search(r"folders/([a-zA-Z0-9_-]+)", valor)
        if match_url:
            return match_url.group(1)
        if re.match(r"^[a-zA-Z0-9_-]{20,}$", valor) and not valor.startswith("http"):
            return valor
        return None

    def listar_fotos(self, nome_pasta: str) -> list[RespostaDrive]:
        token = self._obter_token_valido()

        id_pasta = self._extrair_id_pasta(nome_pasta)
        if not id_pasta:
            id_pasta = self._buscar_pasta_id(token, nome_pasta)

        if not id_pasta:
            raise ValueError("Pasta do Google Drive não encontrada")

        return self._buscar_fotos_drive(token, id_pasta)

    def baixar_imagem(self, file_id: str) -> tuple[str, Iterator[bytes]]:
        """
        Baixa os bytes de um arquivo do Drive (files.get_media via alt=media)
        usando as credenciais do servidor. Retorna o Content-Type e um gerador
        que transmite o conteudo em blocos, fechando a conexao ao final.

        Lanca ValueError se o arquivo nao existir/sem acesso (404) e RuntimeError
        para demais falhas do Drive.
        """
        token = self._obter_token_valido()

        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"

        requisicao = Request(url)
        requisicao.add_header("Authorization", f"Bearer {token}")

        try:
            resposta = urlopen(requisicao, timeout=15)

        except HTTPError as erro:
            if erro.code == 404:
                raise ValueError("Imagem não encontrada no Google Drive") from erro
            raise RuntimeError(
                "Falha ao baixar imagem do Google Drive"
            ) from erro

        except URLError as erro:
            raise RuntimeError(
                "Falha ao baixar imagem do Google Drive"
            ) from erro

        content_type = resposta.headers.get(
            "Content-Type", "application/octet-stream"
        )

        def gerar_blocos() -> Iterator[bytes]:
            try:
                while True:
                    bloco = resposta.read(64 * 1024)
                    if not bloco:
                        break
                    yield bloco
            finally:
                resposta.close()

        return content_type, gerar_blocos()

    def obter_imagem_com_cache(
        self,
        banco: Session,
        file_id: str,
    ) -> tuple[str, bytes]:
        """
        Devolve (content_type, bytes) de uma imagem do Drive servindo do cache
        no banco quando disponivel. No primeiro acesso baixa do Drive, grava o
        conteudo em base64 na tabela imagem_cache e passa a servir do banco nas
        proximas requisicoes.

        Lanca ValueError (404) e RuntimeError (502) iguais a baixar_imagem.
        """
        cache = banco.get(ImagemCache, file_id)
        if cache is not None:
            return cache.content_type, base64.b64decode(cache.conteudo_base64)

        content_type, gerador = self.baixar_imagem(file_id)
        conteudo = b"".join(gerador)

        registro = ImagemCache(
            file_id=file_id,
            content_type=content_type,
            conteudo_base64=base64.b64encode(conteudo).decode("ascii"),
        )
        banco.add(registro)
        try:
            banco.commit()
        except IntegrityError:
            # Outra requisicao gravou o mesmo file_id em paralelo: ignoramos
            # o conflito e seguimos com os bytes ja baixados.
            banco.rollback()

        return content_type, conteudo
