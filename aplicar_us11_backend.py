from pathlib import Path
import sys

RAIZ = Path.cwd()

def ler(relativo: str) -> str:
    caminho = RAIZ / relativo
    if not caminho.exists():
        sys.exit(f"Erro: arquivo nao encontrado: {caminho}")
    return caminho.read_text(encoding="utf-8").replace("\r\n", "\n")

def gravar(relativo: str, conteudo: str) -> None:
    caminho = RAIZ / relativo
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(conteudo, encoding="utf-8", newline="\n")
    print(f"  [OK] {relativo}")

def substituir_uma_vez(relativo: str, antigo: str, novo: str) -> None:
    texto = ler(relativo)
    if novo in texto:
        print(f"  [SKIP] {relativo} (ja aplicado)")
        return
    if antigo not in texto:
        sys.exit(f"Erro: trecho esperado nao encontrado em {relativo}.")
    gravar(relativo, texto.replace(antigo, novo, 1))

MIGRATION = '''"""US11: previa visual nos materiais (link_preview opcional)

Revision ID: f4c9a2e7b1d8
Revises: a1b2c3d4e5f7
Create Date: 2026-11-23 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "f4c9a2e7b1d8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("material", sa.Column("link_preview", sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column("material", "link_preview")
'''

MATERIAL_SCHEMA = '''from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from src.drive.utils import link_de_download, link_de_preview

class TipoMaterial(str, Enum):
    FOTO = "foto"
    VIDEO = "video"
    DOCUMENTO = "documento"

class SolicitacaoMaterial(BaseModel):
    titulo: str
    descricao: str | None = None
    tipo: TipoMaterial
    link: str
    link_preview: str | None = None

    @field_validator("titulo")
    @classmethod
    def _titulo_obrigatorio(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("O título é obrigatório.")
        return valor

    @field_validator("descricao", mode="before")
    @classmethod
    def _descricao_vazia_para_nulo(cls, valor):
        if isinstance(valor, str):
            return valor.strip() or None
        return valor

    @field_validator("link")
    @classmethod
    def _link_http(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor.startswith(("https://", "http://")):
            raise ValueError("O link deve começar com https:// ou http://.")
        return valor

    @field_validator("link_preview", mode="before")
    @classmethod
    def _link_preview_opcional(cls, valor):
        if valor is None:
            return None
        if not isinstance(valor, str):
            return valor
        valor = valor.strip()
        if not valor:
            return None
        return cls._link_http(valor)

class RespostaMaterial(BaseModel):
    material_id: int
    titulo: str
    descricao: str | None = None
    tipo: TipoMaterial
    link: str
    link_preview: str | None = None
    url_download: str = ""
    url_preview: str | None = None
    criado_em: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _preencher_links(self):
        if not self.url_download:
            self.url_download = link_de_download(self.link)
        if not self.url_preview:
            self.url_preview = link_de_preview(self.link, self.tipo.value, self.link_preview)
        return self
'''

DRIVE_UTILS_EXTRA = '''
_HOSTS_YOUTUBE = ("youtube.com", "youtu.be")
_REGEX_YOUTUBE_ID = re.compile(r"^[a-zA-Z0-9_-]{6,20}$")

def extrair_id_youtube(link: str | None) -> str | None:
    if not link:
        return None
    parsed = urlparse(link.strip())
    host = parsed.netloc.lower()
    if not any(host == d or host.endswith("." + d) for d in _HOSTS_YOUTUBE):
        return None
    if host == "youtu.be" or host.endswith(".youtu.be"):
        candidato = parsed.path.lstrip("/").split("/", 1)[0]
    else:
        candidato = parse_qs(parsed.query).get("v", [""])[0]
        if not candidato:
            partes = [p for p in parsed.path.split("/") if p]
            if len(partes) >= 2 and partes[0] in ("shorts", "embed", "live"):
                candidato = partes[1]
    return candidato if _REGEX_YOUTUBE_ID.fullmatch(candidato or "") else None

def montar_url_miniatura(file_id: str) -> str:
    base = configuracoes.BASE_URL.rstrip("/")
    return f"{base}/drive/miniatura/{file_id}"

def link_de_preview(link: str | None, tipo: str | None = None, link_preview: str | None = None) -> str | None:
    if link_preview and link_preview.strip():
        return converter_link_para_proxy(link_preview.strip())
    file_id = extrair_file_id_do_google(link)
    if file_id:
        if tipo == "foto":
            return montar_url_proxy(file_id)
        return montar_url_miniatura(file_id)
    video_id = extrair_id_youtube(link)
    if video_id:
        return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    if tipo == "foto" and link and link.strip():
        return link.strip()
    return None
'''

SERVICE_CACHE_OLD = '''    def obter_imagem_com_cache(
        self,
        banco: Session,
        file_id: str,
    ) -> tuple[str, bytes]:
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
            banco.rollback()
        return content_type, conteudo'''

SERVICE_CACHE_NEW = '''    def _buscar_ou_gravar_cache(self, banco: Session, chave_cache: str, carregar) -> tuple[str, bytes]:
        cache = banco.get(ImagemCache, chave_cache)
        if cache is not None:
            return cache.content_type, base64.b64decode(cache.conteudo_base64)
        content_type, conteudo = carregar()
        registro = ImagemCache(
            file_id=chave_cache,
            content_type=content_type,
            conteudo_base64=base64.b64encode(conteudo).decode("ascii"),
        )
        banco.add(registro)
        try:
            banco.commit()
        except IntegrityError:
            banco.rollback()
        return content_type, conteudo

    def obter_imagem_com_cache(self, banco: Session, file_id: str) -> tuple[str, bytes]:
        def _baixar():
            content_type, gerador = self.baixar_imagem(file_id)
            return content_type, b"".join(gerador)
        return self._buscar_ou_gravar_cache(banco, file_id, _baixar)

    def _ler_metadados_miniatura(self, file_id: str, token: str) -> dict:
        url_meta = (
            f"https://www.googleapis.com/drive/v3/files/{file_id}?"
            f"{urlencode({'fields': 'id,mimeType,thumbnailLink'})}"
        )
        req_meta = Request(url_meta)
        req_meta.add_header("Authorization", f"Bearer {token}")
        req_meta.add_header("Accept", "application/json")
        try:
            with urlopen(req_meta, timeout=10) as resposta:
                return json.loads(resposta.read().decode("utf-8"))
        except HTTPError as erro:
            if erro.code == 404:
                raise ValueError("Arquivo não encontrado no Google Drive") from erro
            raise RuntimeError("Falha ao consultar miniatura no Google Drive") from erro
        except URLError as erro:
            raise RuntimeError("Falha ao consultar miniatura no Google Drive") from erro

    def baixar_miniatura(self, file_id: str) -> tuple[str, bytes]:
        token = self._obter_token_valido()
        dados = self._ler_metadados_miniatura(file_id, token)
        thumb_url = dados.get("thumbnailLink")
        mime_type = dados.get("mimeType") or ""
        if not thumb_url:
            if mime_type.startswith("image/"):
                content_type, gerador = self.baixar_imagem(file_id)
                return content_type, b"".join(gerador)
            raise ValueError("Miniatura não disponível para este arquivo.")
        req_thumb = Request(thumb_url.replace("=s220", "=s800"))
        req_thumb.add_header("Authorization", f"Bearer {token}")
        try:
            with urlopen(req_thumb, timeout=15) as resposta:
                return resposta.headers.get("Content-Type", "image/jpeg"), resposta.read()
        except HTTPError as erro:
            if erro.code == 404:
                raise ValueError("Miniatura não encontrada no Google Drive") from erro
            raise RuntimeError("Falha ao baixar miniatura do Google Drive") from erro
        except URLError as erro:
            raise RuntimeError("Falha ao baixar miniatura do Google Drive") from erro

    def obter_miniatura_com_cache(self, banco: Session, file_id: str) -> tuple[str, bytes]:
        return self._buscar_ou_gravar_cache(banco, f"thumb:{file_id}", lambda: self.baixar_miniatura(file_id))'''

CTRL_ANCHOR = '@router_imagem.get(\n    "/download/{file_id}",'
CTRL_MINIATURA = '''@router_imagem.get(
    "/miniatura/{file_id}",
    responses={
        200: {"content": {"image/*": {}}, "description": "Miniatura do material."},
        404: {"description": "Arquivo não cadastrado ou sem miniatura disponível."},
        502: {"description": "Falha ao falar com o Google Drive."},
    },
)
def proxy_miniatura(file_id: str, banco: Session = Depends(obter_banco)):
    if not ServicoMaterial(RepositorioMaterial(banco)).arquivo_cadastrado(file_id):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    servico = ServicoDrive()
    try:
        content_type, conteudo = servico.obter_miniatura_com_cache(banco, file_id)
    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro
    except RuntimeError as erro:
        raise HTTPException(status_code=502, detail=str(erro)) from erro
    return Response(content=conteudo, media_type=content_type, headers={"Cache-Control": "public, max-age=86400"})

'''

TESTS_US11_EXTRA = '''
class TestPreviaVisualMateriais:
    @pytest.mark.parametrize(
        "url,esperado",
        [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ?si=abc", "dQw4w9WgXcQ"),
            ("https://youtube.com/shorts/abcDEF12345", "abcDEF12345"),
            ("https://youtube.com/embed/abcDEF12345", "abcDEF12345"),
            ("https://youtube.com/live/abcDEF12345", "abcDEF12345"),
            ("https://youtube.com/", None),
            ("https://exemplo.org/watch?v=dQw4w9WgXcQ", None),
            ("", None),
            (None, None),
        ],
    )
    def test_extrair_id_youtube(self, url, esperado):
        from src.drive.utils import extrair_id_youtube
        assert extrair_id_youtube(url) == esperado

    def test_preview_automatica_por_tipo(self):
        from src.drive.utils import link_de_preview
        assert link_de_preview(LINK_DRIVE, "foto") == f"{BASE}/drive/imagem/{ID_DRIVE}"
        assert link_de_preview(LINK_DRIVE, "documento") == f"{BASE}/drive/miniatura/{ID_DRIVE}"
        assert link_de_preview(LINK_DRIVE, "video") == f"{BASE}/drive/miniatura/{ID_DRIVE}"
        assert link_de_preview("https://youtu.be/dQw4w9WgXcQ", "video") == "https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
        assert link_de_preview("https://cdn.exemplo.org/banner.png", "foto") == "https://cdn.exemplo.org/banner.png"
        assert link_de_preview("https://exemplo.org/pagina", "documento") is None

    def test_capa_manual_sobrescreve_preview_automatica(self):
        from src.drive.utils import link_de_preview
        capa_drive = "https://drive.google.com/file/d/CapaManual12345/view"
        assert link_de_preview(LINK_DRIVE, "documento", capa_drive) == f"{BASE}/drive/imagem/CapaManual12345"
        assert link_de_preview(LINK_DRIVE, "documento", "https://cdn.exemplo.org/capa.jpg") == "https://cdn.exemplo.org/capa.jpg"

    def test_validacao_link_preview_opcional(self):
        assert material(link_preview="   ").link_preview is None
        assert material(link_preview=None).link_preview is None
        assert material(link_preview="  https://exemplo.org/capa.jpg  ").link_preview == "https://exemplo.org/capa.jpg"
        with pytest.raises(ValidationError):
            material(link_preview="sem-protocolo.jpg")
        with pytest.raises(ValidationError):
            material(link_preview=123)

    def test_resposta_material_preenche_url_preview(self, servico):
        doc = servico.criar_material(material(tipo=TipoMaterial.DOCUMENTO))
        assert RespostaMaterial.model_validate(doc).url_preview == f"{BASE}/drive/miniatura/{ID_DRIVE}"
        capa = "https://cdn.exemplo.org/capa.png"
        doc_capa = servico.criar_material(material(tipo=TipoMaterial.DOCUMENTO, link_preview=capa))
        resp_capa = RespostaMaterial.model_validate(doc_capa)
        assert resp_capa.link_preview == capa
        assert resp_capa.url_preview == capa

    def test_migracao_adiciona_e_remove_link_preview(self):
        from tests.unit.migracoes_teste import colunas_adicionadas, colunas_removidas, operacoes
        assert "link_preview" in colunas_adicionadas(operacoes("f4c9a2e7b1d8", "upgrade"), "material")
        assert "link_preview" in colunas_removidas(operacoes("f4c9a2e7b1d8", "downgrade"), "material")

class TestRotaMiniaturaDrive:
    def test_miniatura_de_material_cadastrado_retorna_imagem(self, banco, servico):
        servico.criar_material(material(tipo=TipoMaterial.DOCUMENTO))
        drive = MagicMock()
        drive.obter_miniatura_com_cache.return_value = ("image/jpeg", b"thumb-bytes")
        with patch("src.drive.controller.ServicoDrive", return_value=drive):
            resposta = _client_download(banco).get(f"/drive/miniatura/{ID_DRIVE}")
        assert resposta.status_code == 200
        assert resposta.content == b"thumb-bytes"

    def test_miniatura_de_arquivo_nao_cadastrado_responde_404(self, banco):
        assert _client_download(banco).get(f"/drive/miniatura/{ID_DRIVE}").status_code == 404

    @pytest.mark.parametrize("erro,status_esperado", [(ValueError("x"), 404), (RuntimeError("x"), 502)])
    def test_miniatura_mapeia_erros_do_drive(self, banco, servico, erro, status_esperado):
        servico.criar_material(material(tipo=TipoMaterial.DOCUMENTO))
        drive = MagicMock()
        drive.obter_miniatura_com_cache.side_effect = erro
        with patch("src.drive.controller.ServicoDrive", return_value=drive):
            assert _client_download(banco).get(f"/drive/miniatura/{ID_DRIVE}").status_code == status_esperado

class TestServicoDriveMiniatura:
    @patch("src.drive.service.urlopen")
    def test_baixa_thumbnail_link_em_alta_resolucao(self, mock_urlopen, servico_drive):
        meta_resp = _resposta_http(json.dumps({"id": ID_DRIVE, "mimeType": "application/pdf", "thumbnailLink": "https://lh3.googleusercontent.com/thumb=s220"}).encode())
        thumb_resp = _resposta_http(b"jpg-bytes")
        thumb_resp.headers = {"Content-Type": "image/jpeg"}
        mock_urlopen.side_effect = [meta_resp, thumb_resp]
        assert servico_drive.baixar_miniatura(ID_DRIVE) == ("image/jpeg", b"jpg-bytes")

    @patch("src.drive.service.urlopen")
    def test_imagem_sem_thumbnail_usa_baixar_imagem(self, mock_urlopen, servico_drive):
        mock_urlopen.return_value = _resposta_http(json.dumps({"id": ID_DRIVE, "mimeType": "image/png"}).encode())
        servico_drive.baixar_imagem = MagicMock(return_value=("image/png", iter([b"img"])))
        assert servico_drive.baixar_miniatura(ID_DRIVE) == ("image/png", b"img")

    @patch("src.drive.service.urlopen")
    def test_documento_sem_thumbnail_lanca_value_error(self, mock_urlopen, servico_drive):
        mock_urlopen.return_value = _resposta_http(json.dumps({"id": ID_DRIVE, "mimeType": "application/pdf"}).encode())
        with pytest.raises(ValueError, match="Miniatura não disponível"):
            servico_drive.baixar_miniatura(ID_DRIVE)

    @pytest.mark.parametrize("erro,esperado", [(HTTPError("u", 404, "nf", {}, None), ValueError), (HTTPError("u", 500, "err", {}, None), RuntimeError), (URLError("sem rede"), RuntimeError)])
    @patch("src.drive.service.urlopen")
    def test_erros_ao_consultar_metadados_da_miniatura(self, mock_urlopen, servico_drive, erro, esperado):
        mock_urlopen.side_effect = erro
        with pytest.raises(esperado):
            servico_drive.baixar_miniatura(ID_DRIVE)

    @pytest.mark.parametrize("erro,esperado", [(HTTPError("u", 404, "nf", {}, None), ValueError), (HTTPError("u", 500, "err", {}, None), RuntimeError), (URLError("sem rede"), RuntimeError)])
    @patch("src.drive.service.urlopen")
    def test_erros_ao_baixar_bytes_da_miniatura(self, mock_urlopen, servico_drive, erro, esperado):
        meta_resp = _resposta_http(json.dumps({"id": ID_DRIVE, "mimeType": "application/pdf", "thumbnailLink": "https://lh3.googleusercontent.com/thumb=s220"}).encode())
        mock_urlopen.side_effect = [meta_resp, erro]
        with pytest.raises(esperado):
            servico_drive.baixar_miniatura(ID_DRIVE)

    def test_obter_miniatura_com_cache_usa_prefixo_thumb(self, servico_drive):
        db_mock = MagicMock()
        db_mock.get.return_value = None
        servico_drive.baixar_miniatura = MagicMock(return_value=("image/png", b"ok"))
        assert servico_drive.obter_miniatura_com_cache(db_mock, ID_DRIVE) == ("image/png", b"ok")
        assert db_mock.get.call_args.args[1] == f"thumb:{ID_DRIVE}"
'''

ENDPOINT_ANCHOR = '''    def test_material_traz_link_de_download_e_data_de_criacao(self, material):
        """`criado_em` vem do banco, nao da aplicacao — so o Postgres responde."""
        assert material["url_download"], "material sem link de download"
        assert material["criado_em"], "material sem data de criacao"'''

ENDPOINT_NEW = ENDPOINT_ANCHOR + '''

    def test_material_traz_url_preview_automatica_e_permite_sobrescrever(self, superadmin):
        criado = superadmin.post(
            "/material/",
            json={"titulo": "Video YouTube", "tipo": "video", "link": "https://youtu.be/dQw4w9WgXcQ"},
        )
        assert criado.status_code == 201, criado.text
        dados = criado.json()
        try:
            assert dados["url_preview"] == "https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
        finally:
            superadmin.delete(f"/material/{dados['material_id']}")'''

def main():
    gravar("migrations/versions/f4c9a2e7b1d8_us11_preview_material.py", MIGRATION)
    substituir_uma_vez("src/material/model.py", "    link        = Column(Text, nullable=False)\n", "    link        = Column(Text, nullable=False)\n    link_preview = Column(Text, nullable=True)\n")
    gravar("src/material/schema.py", MATERIAL_SCHEMA)
    utils_txt = ler("src/drive/utils.py")
    if "def link_de_preview(" not in utils_txt:
        cab = ""
        if "import re" not in utils_txt:
            cab += "import re\n"
        if "parse_qs" not in utils_txt or "urlparse" not in utils_txt:
            cab += "from urllib.parse import parse_qs, urlparse\n"
        gravar("src/drive/utils.py", cab + utils_txt.rstrip() + "\n" + DRIVE_UTILS_EXTRA)
    substituir_uma_vez("src/drive/service.py", SERVICE_CACHE_OLD, SERVICE_CACHE_NEW)
    substituir_uma_vez("src/drive/controller.py", CTRL_ANCHOR, CTRL_MINIATURA + CTRL_ANCHOR)
    substituir_uma_vez("tests/unit/test_matriz_rotas.py", '    ("GET", "/drive/download/{file_id}"): PUBLICA,\n', '    ("GET", "/drive/download/{file_id}"): PUBLICA,\n    ("GET", "/drive/miniatura/{file_id}"): PUBLICA,\n')
    us11_txt = ler("tests/unit/test_us11_materiais.py")
    if "class TestPreviaVisualMateriais" not in us11_txt:
        gravar("tests/unit/test_us11_materiais.py", us11_txt.rstrip() + "\n" + TESTS_US11_EXTRA)
    substituir_uma_vez("tests/endpoint/test_sprint3_postgres.py", ENDPOINT_ANCHOR, ENDPOINT_NEW)

if __name__ == "__main__":
    main()
