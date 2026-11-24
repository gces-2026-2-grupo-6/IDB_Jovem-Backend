"""
US11 — Materiais para download.

* cadastro de materiais (foto, vídeo, documento): leitura pública, escrita
  só da superadministradora;
* url_download em todo material e em toda foto das galerias;
* GET /drive/download/{file_id}: baixa com o nome original, sem login, mas
  só imagem ou arquivo cadastrado como material.
"""

import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import obter_banco
from src.drive.controller import router_imagem
from src.drive.schema import RespostaDrive
from src.drive.service import ServicoDrive
from src.drive.utils import extrair_file_id_do_google, link_de_download
from src.evento.schema import RespostaItemGaleria
from src.material.controller import router as material_router, get_servico
from src.material.model import Material
from src.material.repository import RepositorioMaterial
from src.material.schema import RespostaMaterial, SolicitacaoMaterial, TipoMaterial
from src.material.service import ServicoMaterial
from src.security import obter_usuario_atual

SUPERADMIN = {"sub": "super-1", "realm_access": {"roles": ["superadmin"]}}
ADMIN = {"sub": "admin-1", "realm_access": {"roles": ["admin"]}}

ID_DRIVE = "1AbCdEfGhIjKlMnOpQrStUv"
LINK_DRIVE = f"https://drive.google.com/file/d/{ID_DRIVE}/view?usp=sharing"
BASE = "http://localhost:8000"


@pytest.fixture
def banco():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Material.__table__.create(engine)
    sessao = sessionmaker(bind=engine)()
    yield sessao
    sessao.close()


@pytest.fixture
def servico(banco) -> ServicoMaterial:
    return ServicoMaterial(RepositorioMaterial(banco))


def material(titulo="Logo oficial", tipo=TipoMaterial.FOTO, link=LINK_DRIVE, **extra):
    return SolicitacaoMaterial(titulo=titulo, tipo=tipo, link=link, **extra)


# ------------------------------------------------------------- links de download


class TestLinkDeDownload:

    @pytest.mark.parametrize(
        "link",
        [
            LINK_DRIVE,
            f"https://drive.google.com/open?id={ID_DRIVE}",
            f"https://docs.google.com/document/d/{ID_DRIVE}/edit",
            f"https://lh3.googleusercontent.com/d/{ID_DRIVE}",
            ID_DRIVE,
        ],
    )
    def test_arquivo_do_google_passa_pela_rota_de_download(self, link):
        assert link_de_download(link) == f"{BASE}/drive/download/{ID_DRIVE}"

    @pytest.mark.parametrize(
        "link",
        [
            "https://youtu.be/abc123",
            "https://exemplo.org/d/qualquercoisa/arquivo.pdf",
            "https://exemplo.org/baixar?id=1234567890abc",
        ],
    )
    def test_link_externo_volta_como_esta(self, link):
        assert link_de_download(link) == link

    def test_link_vazio(self):
        assert link_de_download(None) is None
        assert extrair_file_id_do_google("") is None

    def test_foto_da_galeria_do_evento_traz_o_download(self):
        foto = RespostaDrive(id=ID_DRIVE, nome="a.jpg", url_visualizacao="x")
        assert foto.url_download == f"{BASE}/drive/download/{ID_DRIVE}"

    def test_foto_da_galeria_geral_traz_o_download(self):
        item = RespostaItemGaleria(id=ID_DRIVE, image="x", event="Congresso", location="")
        assert item.url_download == f"{BASE}/drive/download/{ID_DRIVE}"

    def test_download_informado_nao_e_sobrescrito(self):
        foto = RespostaDrive(id=ID_DRIVE, nome="a.jpg", url_visualizacao="x", url_download="y")
        assert foto.url_download == "y"


# ------------------------------------------------------------------- validação


class TestValidacao:

    def test_titulo_em_branco_e_recusado(self):
        with pytest.raises(ValidationError):
            material(titulo="   ")

    def test_link_sem_http_e_recusado(self):
        with pytest.raises(ValidationError):
            material(link="drive.google.com/file/d/abc")

    def test_tipo_fora_da_lista_e_recusado(self):
        with pytest.raises(ValidationError):
            SolicitacaoMaterial(titulo="X", tipo="planilha", link=LINK_DRIVE)

    def test_descricao_vazia_vira_nulo(self):
        assert material(descricao="  ").descricao is None

    def test_descricao_e_titulo_sao_aparados(self):
        dados = material(titulo="  Logo  ", descricao="  PNG  ")
        assert (dados.titulo, dados.descricao) == ("Logo", "PNG")

    def test_descricao_nao_texto_segue_para_o_pydantic(self):
        with pytest.raises(ValidationError):
            material(descricao=123)


# --------------------------------------------------------------------- serviço


class TestServico:

    def test_cria_e_lista_com_link_de_download(self, servico):
        criado = servico.criar_material(material())

        resposta = RespostaMaterial.model_validate(criado)

        assert resposta.material_id == 1
        assert resposta.tipo is TipoMaterial.FOTO
        assert resposta.url_download == f"{BASE}/drive/download/{ID_DRIVE}"
        assert resposta.criado_em is not None

    def test_lista_do_mais_novo_para_o_mais_antigo(self, servico):
        servico.criar_material(material(titulo="Primeiro"))
        servico.criar_material(material(titulo="Segundo"))

        titulos = [m.titulo for m in servico.listar_materiais()]

        assert titulos == ["Segundo", "Primeiro"]

    def test_filtra_por_tipo(self, servico):
        servico.criar_material(material(titulo="Foto"))
        servico.criar_material(material(titulo="Video", tipo=TipoMaterial.VIDEO))

        videos = servico.listar_materiais(TipoMaterial.VIDEO)

        assert [m.titulo for m in videos] == ["Video"]

    def test_atualiza(self, servico):
        criado = servico.criar_material(material())

        atualizado = servico.atualizar_material(
            criado.material_id, material(titulo="Logo 2026", tipo=TipoMaterial.DOCUMENTO)
        )

        assert atualizado.titulo == "Logo 2026"
        assert atualizado.tipo == "documento"

    def test_exclui(self, servico):
        criado = servico.criar_material(material())

        servico.deletar_material(criado.material_id)

        assert servico.listar_materiais() == []

    @pytest.mark.parametrize("acao", ["buscar", "atualizar", "deletar"])
    def test_material_inexistente(self, servico, acao):
        with pytest.raises(ValueError, match="Material não encontrado"):
            if acao == "atualizar":
                servico.atualizar_material(99, material())
            else:
                getattr(servico, f"{acao}_material")(99)

    def test_arquivo_cadastrado(self, servico):
        servico.criar_material(material())
        servico.criar_material(material(link="https://youtu.be/abc"))

        assert servico.arquivo_cadastrado(ID_DRIVE) is True
        assert servico.arquivo_cadastrado("OutroArquivo123456") is False


# ----------------------------------------------------------------- rotas /material


def _client_material(servico_material, usuario=None):
    app = FastAPI()
    app.include_router(material_router)
    app.dependency_overrides[get_servico] = lambda: servico_material
    if usuario is not None:
        app.dependency_overrides[obter_usuario_atual] = lambda: usuario
    return TestClient(app)


class TestRotasMaterial:

    def test_visitante_sem_login_lista_e_ve_o_download(self, servico):
        servico.criar_material(material())

        resposta = _client_material(servico).get("/material/")

        assert resposta.status_code == 200
        [item] = resposta.json()
        assert item["titulo"] == "Logo oficial"
        assert item["tipo"] == "foto"
        assert item["url_download"] == f"{BASE}/drive/download/{ID_DRIVE}"

    def test_filtro_por_tipo_na_rota(self, servico):
        servico.criar_material(material())

        resposta = _client_material(servico).get("/material/?tipo=video")

        assert resposta.json() == []

    def test_busca_por_id(self, servico):
        criado = servico.criar_material(material())
        cliente = _client_material(servico)

        assert cliente.get(f"/material/{criado.material_id}").status_code == 200
        assert cliente.get("/material/99").status_code == 404

    def test_superadmin_cria_edita_e_exclui(self, servico):
        cliente = _client_material(servico, SUPERADMIN)
        corpo = {"titulo": "Manual", "tipo": "documento", "link": LINK_DRIVE}

        criado = cliente.post("/material/", json=corpo)
        assert criado.status_code == 201
        material_id = criado.json()["material_id"]

        editado = cliente.put(f"/material/{material_id}", json={**corpo, "titulo": "Manual 2"})
        assert editado.json()["titulo"] == "Manual 2"

        assert cliente.delete(f"/material/{material_id}").status_code == 204
        assert cliente.get("/material/").json() == []

    def test_editar_ou_excluir_inexistente_responde_404(self, servico):
        cliente = _client_material(servico, SUPERADMIN)
        corpo = {"titulo": "Manual", "tipo": "documento", "link": LINK_DRIVE}

        assert cliente.put("/material/99", json=corpo).status_code == 404
        assert cliente.delete("/material/99").status_code == 404

    @pytest.mark.parametrize(
        "metodo,caminho",
        [("post", "/material/"), ("put", "/material/1"), ("delete", "/material/1")],
    )
    def test_admin_de_setor_nao_envia_nem_exclui(self, servico, metodo, caminho):
        """CA2: o servidor recusa mesmo que a ação seja tentada direto."""
        corpo = {"titulo": "Manual", "tipo": "documento", "link": LINK_DRIVE}
        cliente = _client_material(servico, ADMIN)

        kwargs = {} if metodo == "delete" else {"json": corpo}
        resposta = getattr(cliente, metodo)(caminho, **kwargs)

        assert resposta.status_code == 403


def test_injecao_do_servico_usa_o_banco_da_requisicao():
    db = MagicMock()
    assert get_servico(db).repositorio.db is db


# -------------------------------------------------------- GET /drive/download


def _client_download(banco):
    app = FastAPI()
    app.include_router(router_imagem)
    app.dependency_overrides[obter_banco] = lambda: banco
    return TestClient(app)


def _drive_falso(content_type="image/jpeg", nome="foto.jpg", conteudo=b"bytes"):
    drive = MagicMock()
    drive.obter_metadados.return_value = {"nome": nome, "content_type": content_type}
    drive.transmitir_arquivo.return_value = (nome, content_type, iter([conteudo]))
    return drive


class TestRotaDeDownload:

    def test_foto_e_baixada_com_o_nome_original(self, banco):
        drive = _drive_falso(nome="Congresso 2026 — palco.jpg")
        with patch("src.drive.controller.ServicoDrive", return_value=drive):
            resposta = _client_download(banco).get(f"/drive/download/{ID_DRIVE}")

        assert resposta.status_code == 200
        assert resposta.content == b"bytes"
        assert resposta.headers["content-type"] == "image/jpeg"
        disposicao = resposta.headers["content-disposition"]
        assert disposicao.startswith("attachment;")
        assert "Congresso%202026%20%E2%80%94%20palco.jpg" in disposicao

    def test_documento_cadastrado_como_material_e_baixado(self, banco, servico):
        servico.criar_material(material(tipo=TipoMaterial.DOCUMENTO))
        drive = _drive_falso(content_type="application/pdf", nome="manual.pdf")

        with patch("src.drive.controller.ServicoDrive", return_value=drive):
            resposta = _client_download(banco).get(f"/drive/download/{ID_DRIVE}")

        assert resposta.status_code == 200
        drive.transmitir_arquivo.assert_called_once()

    def test_documento_que_nao_e_material_nao_sai(self, banco):
        """
        A rota usa a conta institucional: sem esta trava, quem souber o id
        baixaria qualquer arquivo dela, como a planilha de líderes.
        """
        drive = _drive_falso(content_type="application/vnd.ms-excel", nome="lideres.xlsx")

        with patch("src.drive.controller.ServicoDrive", return_value=drive):
            resposta = _client_download(banco).get(f"/drive/download/{ID_DRIVE}")

        assert resposta.status_code == 404
        drive.transmitir_arquivo.assert_not_called()

    def test_arquivo_inexistente_responde_404(self, banco):
        drive = MagicMock()
        drive.obter_metadados.side_effect = ValueError("Arquivo não encontrado no Google Drive")

        with patch("src.drive.controller.ServicoDrive", return_value=drive):
            resposta = _client_download(banco).get(f"/drive/download/{ID_DRIVE}")

        assert resposta.status_code == 404

    def test_falha_do_drive_responde_502(self, banco):
        drive = MagicMock()
        drive.obter_metadados.side_effect = RuntimeError("Falha ao consultar arquivo no Google Drive")

        with patch("src.drive.controller.ServicoDrive", return_value=drive):
            resposta = _client_download(banco).get(f"/drive/download/{ID_DRIVE}")

        assert resposta.status_code == 502


# ----------------------------------------------------- ServicoDrive (download)


def _resposta_http(corpo: bytes):
    resposta = MagicMock()
    resposta.read.side_effect = [corpo, b""]
    resposta.__enter__.return_value = resposta
    return resposta


@pytest.fixture
def servico_drive():
    with patch("src.drive.service.ServicoAuth") as auth:
        auth.return_value.obter_credenciais_validas.return_value.token = "tok"
        drive = ServicoDrive()
        drive.refresh_token = "refresh"
        yield drive


class TestServicoDriveDownload:

    @patch("src.drive.service.urlopen")
    def test_metadados_pede_nome_e_tipo_com_o_token(self, mock_urlopen, servico_drive):
        mock_urlopen.return_value = _resposta_http(
            json.dumps({"name": "manual.pdf", "mimeType": "application/pdf"}).encode()
        )

        meta = servico_drive.obter_metadados(ID_DRIVE)

        assert meta == {"nome": "manual.pdf", "content_type": "application/pdf"}
        requisicao = mock_urlopen.call_args.args[0]
        assert requisicao.get_header("Authorization") == "Bearer tok"
        assert ID_DRIVE in requisicao.full_url
        assert "fields=id%2Cname%2CmimeType" in requisicao.full_url

    @patch("src.drive.service.urlopen")
    def test_metadados_sem_nome_usam_o_id(self, mock_urlopen, servico_drive):
        mock_urlopen.return_value = _resposta_http(b"{}")

        meta = servico_drive.obter_metadados(ID_DRIVE)

        assert meta == {"nome": ID_DRIVE, "content_type": "application/octet-stream"}

    @pytest.mark.parametrize(
        "erro,esperado",
        [
            (HTTPError("u", 404, "nf", {}, None), ValueError),
            (HTTPError("u", 403, "proibido", {}, None), RuntimeError),
            (URLError("sem rede"), RuntimeError),
        ],
    )
    @patch("src.drive.service.urlopen")
    def test_metadados_erros(self, mock_urlopen, servico_drive, erro, esperado):
        mock_urlopen.side_effect = erro
        with pytest.raises(esperado):
            servico_drive.obter_metadados(ID_DRIVE)

    @patch("src.drive.service.urlopen")
    def test_arquivo_comum_baixa_com_alt_media(self, mock_urlopen, servico_drive):
        resposta = MagicMock()
        resposta.read.side_effect = [b"parte1", b"parte2", b""]
        mock_urlopen.return_value = resposta

        nome, tipo, blocos = servico_drive.transmitir_arquivo(
            ID_DRIVE, {"nome": "video.mp4", "content_type": "video/mp4"}
        )

        assert (nome, tipo) == ("video.mp4", "video/mp4")
        assert b"".join(blocos) == b"parte1parte2"
        resposta.close.assert_called_once()
        requisicao = mock_urlopen.call_args.args[0]
        assert requisicao.full_url.endswith(f"{ID_DRIVE}?alt=media")
        assert requisicao.get_header("Authorization") == "Bearer tok"

    @patch("src.drive.service.urlopen")
    def test_documento_do_google_e_exportado_em_pdf(self, mock_urlopen, servico_drive):
        mock_urlopen.return_value = _resposta_http(b"%PDF")

        nome, tipo, _ = servico_drive.transmitir_arquivo(
            ID_DRIVE,
            {"nome": "Regulamento", "content_type": "application/vnd.google-apps.document"},
        )

        assert (nome, tipo) == ("Regulamento.pdf", "application/pdf")
        url = mock_urlopen.call_args.args[0].full_url
        assert f"{ID_DRIVE}/export?mimeType=application%2Fpdf" in url

    @patch("src.drive.service.urlopen")
    def test_nome_que_ja_termina_em_pdf_nao_ganha_outra_extensao(self, mock_urlopen, servico_drive):
        mock_urlopen.return_value = _resposta_http(b"%PDF")

        nome, _, _ = servico_drive.transmitir_arquivo(
            ID_DRIVE,
            {"nome": "Manual.PDF", "content_type": "application/vnd.google-apps.document"},
        )

        assert nome == "Manual.PDF"

    @pytest.mark.parametrize(
        "erro,esperado",
        [
            (HTTPError("u", 404, "nf", {}, None), ValueError),
            (HTTPError("u", 500, "erro", {}, None), RuntimeError),
            (URLError("sem rede"), RuntimeError),
        ],
    )
    @patch("src.drive.service.urlopen")
    def test_download_erros(self, mock_urlopen, servico_drive, erro, esperado):
        mock_urlopen.side_effect = erro
        with pytest.raises(esperado):
            servico_drive.transmitir_arquivo(
                ID_DRIVE, {"nome": "a.mp4", "content_type": "video/mp4"}
            )

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
