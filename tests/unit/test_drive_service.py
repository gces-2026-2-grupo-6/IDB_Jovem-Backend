import pytest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError
from src.drive.service import ServicoDrive


class TestServicoDrive:
    def setup_method(self):
        ServicoDrive.limpar_cache()

    @patch.dict("os.environ", {"GOOGLE_REFRESH_TOKEN": ""})
    @patch("src.drive.service.ServicoAuth")
    def test_obter_token_sem_refresh(self, mock_auth_class):
        servico = ServicoDrive()
        servico.refresh_token = None
        with pytest.raises(RuntimeError, match="GOOGLE_REFRESH_TOKEN nao configurado"):
            servico._obter_token_valido()

    @patch.dict("os.environ", {"GOOGLE_REFRESH_TOKEN": "token-123"})
    @patch("src.drive.service.ServicoAuth")
    def test_obter_token_sucesso(self, mock_auth_class):
        mock_auth = MagicMock()
        mock_creds = MagicMock()
        mock_creds.token = "access-token"
        mock_auth.obter_credenciais_validas.return_value = mock_creds
        mock_auth_class.return_value = mock_auth

        servico = ServicoDrive()
        resultado = servico._obter_token_valido()
        assert resultado == "access-token"

    @patch.dict("os.environ", {"GOOGLE_REFRESH_TOKEN": "token-123"})
    @patch("src.drive.service.ServicoAuth")
    def test_obter_token_falha(self, mock_auth_class):
        mock_auth = MagicMock()
        mock_auth.obter_credenciais_validas.side_effect = Exception("Erro")
        mock_auth_class.return_value = mock_auth

        servico = ServicoDrive()
        with pytest.raises(RuntimeError, match="Falha automatica ao renovar credenciais"):
            servico._obter_token_valido()

    @patch("src.drive.service.ServicoAuth")
    def test_montar_url_busca_pasta(self, mock_auth_class):
        servico = ServicoDrive()
        url = servico._montar_url_busca_pasta("MinhasPastas")
        assert "googleapis.com/drive/v3/files" in url
        assert "MinhasPastas" in url

    @patch("src.drive.service.ServicoAuth")
    def test_montar_url_busca_fotos(self, mock_auth_class):
        servico = ServicoDrive()
        url = servico._montar_url_busca_fotos("folder-id-123")
        assert "googleapis.com/drive/v3/files" in url
        assert "folder-id-123" in url

    @patch("src.drive.service.ServicoAuth")
    def test_montar_url_visualizacao(self, mock_auth_class):
        servico = ServicoDrive()
        url = servico._montar_url_visualizacao("file-id-123")
        assert url.endswith("/drive/imagem/file-id-123")

    @patch("src.drive.service.urlopen")
    @patch("src.drive.service.ServicoAuth")
    def test_baixar_imagem_sucesso(self, mock_auth_class, mock_urlopen):
        mock_resposta = MagicMock()
        mock_resposta.headers.get.return_value = "image/jpeg"
        mock_resposta.read.side_effect = [b"dados", b""]
        mock_urlopen.return_value = mock_resposta

        servico = ServicoDrive()
        servico._obter_token_valido = MagicMock(return_value="token")

        content_type, conteudo = servico.baixar_imagem("file-id-123")
        assert content_type == "image/jpeg"
        assert b"".join(conteudo) == b"dados"
        mock_resposta.close.assert_called_once()

    @patch("src.drive.service.urlopen")
    @patch("src.drive.service.ServicoAuth")
    def test_baixar_imagem_nao_encontrada(self, mock_auth_class, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="http://test.com", code=404, msg="Not Found", hdrs=None, fp=None
        )
        servico = ServicoDrive()
        servico._obter_token_valido = MagicMock(return_value="token")

        with pytest.raises(ValueError, match="não encontrada"):
            servico.baixar_imagem("inexistente")

    @patch("src.drive.service.urlopen")
    @patch("src.drive.service.ServicoAuth")
    def test_baixar_imagem_erro_drive(self, mock_auth_class, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="http://test.com", code=500, msg="Error", hdrs=None, fp=None
        )
        servico = ServicoDrive()
        servico._obter_token_valido = MagicMock(return_value="token")

        with pytest.raises(RuntimeError, match="Falha ao baixar imagem"):
            servico.baixar_imagem("file-id-123")

    @patch("src.drive.service.urlopen")
    @patch("src.drive.service.ServicoAuth")
    def test_buscar_pasta_id_sucesso(self, mock_auth_class, mock_urlopen):
        import json
        mock_resposta = MagicMock()
        mock_resposta.read.return_value = json.dumps({
            "files": [{"id": "folder-id-123", "name": "Pasta"}]
        }).encode("utf-8")
        mock_resposta.__enter__ = lambda s: s
        mock_resposta.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resposta

        servico = ServicoDrive()
        resultado = servico._buscar_pasta_id("token", "Pasta")
        assert resultado == "folder-id-123"

    @patch("src.drive.service.urlopen")
    @patch("src.drive.service.ServicoAuth")
    def test_buscar_pasta_id_nao_encontrada(self, mock_auth_class, mock_urlopen):
        import json
        mock_resposta = MagicMock()
        mock_resposta.read.return_value = json.dumps({"files": []}).encode("utf-8")
        mock_resposta.__enter__ = lambda s: s
        mock_resposta.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resposta

        servico = ServicoDrive()
        resultado = servico._buscar_pasta_id("token", "Inexistente")
        assert resultado is None

    @patch("src.drive.service.urlopen")
    @patch("src.drive.service.ServicoAuth")
    def test_buscar_pasta_id_http_error(self, mock_auth_class, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="http://test.com", code=500, msg="Error", hdrs=None, fp=None
        )
        servico = ServicoDrive()
        with pytest.raises(RuntimeError, match="Falha ao buscar pasta"):
            servico._buscar_pasta_id("token", "Pasta")

    @patch("src.drive.service.urlopen")
    @patch("src.drive.service.ServicoAuth")
    def test_buscar_fotos_drive_sucesso(self, mock_auth_class, mock_urlopen):
        import json
        mock_resposta = MagicMock()
        mock_resposta.read.return_value = json.dumps({
            "files": [
                {"id": "file-1", "name": "foto1.jpg", "mimeType": "image/jpeg"},
                {"id": "file-2", "name": "foto2.png", "mimeType": "image/png"},
            ]
        }).encode("utf-8")
        mock_resposta.__enter__ = lambda s: s
        mock_resposta.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resposta

        servico = ServicoDrive()
        resultado = servico._buscar_fotos_drive("token", "folder-id")
        assert len(resultado) == 2
        assert resultado[0].nome == "foto1.jpg"

    @patch("src.drive.service.urlopen")
    @patch("src.drive.service.ServicoAuth")
    def test_buscar_fotos_drive_sem_id(self, mock_auth_class, mock_urlopen):
        import json
        mock_resposta = MagicMock()
        mock_resposta.read.return_value = json.dumps({
            "files": [{"name": "foto1.jpg", "mimeType": "image/jpeg"}]
        }).encode("utf-8")
        mock_resposta.__enter__ = lambda s: s
        mock_resposta.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resposta

        servico = ServicoDrive()
        resultado = servico._buscar_fotos_drive("token", "folder-id")
        assert len(resultado) == 0

    @patch("src.drive.service.urlopen")
    @patch("src.drive.service.ServicoAuth")
    def test_buscar_fotos_drive_http_error(self, mock_auth_class, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="http://test.com", code=500, msg="Error", hdrs=None, fp=None
        )
        servico = ServicoDrive()
        with pytest.raises(RuntimeError, match="Falha ao buscar fotos"):
            servico._buscar_fotos_drive("token", "folder-id")

    @patch("src.drive.service.ServicoAuth")
    def test_listar_fotos_sucesso(self, mock_auth_class):
        servico = ServicoDrive()
        servico._obter_token_valido = MagicMock(return_value="token")
        servico._buscar_pasta_id = MagicMock(return_value="folder-id")
        servico._buscar_fotos_drive = MagicMock(return_value=[])

        resultado = servico.listar_fotos("Pasta")
        servico._buscar_fotos_drive.assert_called_once_with("token", "folder-id")

    @patch("src.drive.service.ServicoAuth")
    def test_listar_fotos_pasta_nao_encontrada(self, mock_auth_class):
        servico = ServicoDrive()
        servico._obter_token_valido = MagicMock(return_value="token")
        servico._buscar_pasta_id = MagicMock(return_value=None)

        with pytest.raises(ValueError, match="Pasta do Google Drive não encontrada"):
            servico.listar_fotos("Inexistente")

    @patch("src.drive.service.ServicoAuth")
    def test_extrair_id_pasta(self, mock_auth_class):
        servico = ServicoDrive()
        url = "https://drive.google.com/drive/folders/1ABC_xyz-1234567890abcdef"
        assert servico._extrair_id_pasta(url) == "1ABC_xyz-1234567890abcdef"

        direto = "1ABC_xyz-1234567890abcdef"
        assert servico._extrair_id_pasta(direto) == "1ABC_xyz-1234567890abcdef"

        assert servico._extrair_id_pasta("Pasta Com Nome") is None
        assert servico._extrair_id_pasta("") is None

    @patch("src.drive.service.ServicoAuth")
    def test_listar_fotos_com_url_do_drive(self, mock_auth_class):
        servico = ServicoDrive()
        servico._obter_token_valido = MagicMock(return_value="token")
        servico._buscar_pasta_id = MagicMock()
        servico._buscar_fotos_drive = MagicMock(return_value=[])

        url = "https://drive.google.com/drive/folders/1ABC_xyz-1234567890abcdef"
        servico.listar_fotos(url)
        # Nao deve chamar _buscar_pasta_id pois o id foi extraido da URL
        servico._buscar_pasta_id.assert_not_called()
        servico._buscar_fotos_drive.assert_called_once_with("token", "1ABC_xyz-1234567890abcdef")

    @patch("src.drive.service.urlopen")
    @patch("src.drive.service.ServicoAuth")
    def test_buscar_fotos_drive_cache(self, mock_auth_class, mock_urlopen):
        import json
        mock_resposta = MagicMock()
        mock_resposta.read.return_value = json.dumps({
            "files": [{"id": "f1", "name": "foto1.jpg"}]
        }).encode("utf-8")
        mock_resposta.__enter__ = lambda s: s
        mock_resposta.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resposta

        servico = ServicoDrive()
        res1 = servico._buscar_fotos_drive("token", "folder-cache")
        assert len(res1) == 1
        assert mock_urlopen.call_count == 1

        # Segunda chamada deve vir do cache sem chamar urlopen
        res2 = servico._buscar_fotos_drive("token", "folder-cache")
        assert len(res2) == 1
        assert mock_urlopen.call_count == 1

    @patch("src.drive.service.urlopen")
    @patch("src.drive.service.ServicoAuth")
    def test_buscar_fotos_drive_paginacao(self, mock_auth_class, mock_urlopen):
        import json
        resp1 = MagicMock()
        resp1.read.return_value = json.dumps({
            "files": [{"id": "p1", "name": "pagina1.jpg"}],
            "nextPageToken": "token-pag-2"
        }).encode("utf-8")
        resp1.__enter__ = lambda s: s
        resp1.__exit__ = MagicMock(return_value=False)

        resp2 = MagicMock()
        resp2.read.return_value = json.dumps({
            "files": [{"id": "p2", "name": "pagina2.jpg"}]
        }).encode("utf-8")
        resp2.__enter__ = lambda s: s
        resp2.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [resp1, resp2]

        servico = ServicoDrive()
        resultado = servico._buscar_fotos_drive("token", "folder-pag")
        assert len(resultado) == 2
        assert resultado[0].id == "p1"
        assert resultado[1].id == "p2"
        assert mock_urlopen.call_count == 2

