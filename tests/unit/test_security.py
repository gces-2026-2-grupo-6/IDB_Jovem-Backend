import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException

from src.security import (
    _parse_audiences,
    _carregar_config_keycloak,
    _obter_cliente_jwks,
    obter_usuario_atual,
    verificar_roles,
)


class TestParseAudiences:
    def test_com_valores(self):
        resultado = _parse_audiences("aud1,aud2", "client-id")
        assert "aud1" in resultado
        assert "aud2" in resultado
        assert "client-id" in resultado
        assert "account" in resultado

    def test_sem_valor(self):
        resultado = _parse_audiences("", "client-id")
        assert "client-id" in resultado
        assert "account" in resultado

    def test_client_id_ja_presente(self):
        resultado = _parse_audiences("client-id,aud1", "client-id")
        assert resultado.count("client-id") == 1

    def test_account_ja_presente(self):
        resultado = _parse_audiences("account", "client-id")
        assert resultado.count("account") == 1

    def test_sem_client_id(self):
        resultado = _parse_audiences("aud1", "")
        assert "aud1" in resultado
        assert "account" in resultado

    def test_valores_com_espacos(self):
        resultado = _parse_audiences(" aud1 , aud2 , ", "client-id")
        assert "aud1" in resultado
        assert "aud2" in resultado


class TestCarregarConfigKeycloak:
    @patch("src.security.configuracoes")
    def test_com_issuer_e_jwks_url(self, mock_config):
        mock_config.KEYCLOAK_URL = "http://keycloak.local"
        mock_config.KEYCLOAK_REALM = "myrealm"
        mock_config.KEYCLOAK_CLIENT_ID = "my-client"
        mock_config.KEYCLOAK_ISSUER = "http://keycloak.local/realms/myrealm"
        mock_config.KEYCLOAK_JWKS_URL = "http://keycloak.local/realms/myrealm/protocol/openid-connect/certs"
        mock_config.KEYCLOAK_AUDIENCE = "aud1"

        issuer, jwks_url, client_id, audiencia = _carregar_config_keycloak()

        assert issuer == "http://keycloak.local/realms/myrealm"
        assert jwks_url == "http://keycloak.local/realms/myrealm/protocol/openid-connect/certs"
        assert client_id == "my-client"

    @patch("src.security.configuracoes")
    def test_sem_issuer_gera_automaticamente(self, mock_config):
        mock_config.KEYCLOAK_URL = "http://keycloak.local/"
        mock_config.KEYCLOAK_REALM = "myrealm"
        mock_config.KEYCLOAK_CLIENT_ID = "my-client"
        mock_config.KEYCLOAK_ISSUER = ""
        mock_config.KEYCLOAK_JWKS_URL = ""
        mock_config.KEYCLOAK_AUDIENCE = ""

        issuer, jwks_url, client_id, audiencia = _carregar_config_keycloak()

        assert issuer == "http://keycloak.local/realms/myrealm"
        assert jwks_url == "http://keycloak.local/realms/myrealm/protocol/openid-connect/certs"


class TestObterClienteJwks:
    @patch("src.security._JWKS_CLIENT", None)
    @patch("src.security._JWKS_URL", None)
    @patch("src.security.PyJWKClient")
    def test_cria_novo_cliente(self, mock_jwk_client_class):
        mock_client = MagicMock()
        mock_jwk_client_class.return_value = mock_client

        resultado = _obter_cliente_jwks("http://example.com/certs")

        mock_jwk_client_class.assert_called_once_with("http://example.com/certs")
        assert resultado == mock_client


class TestObterUsuarioAtual:
    @pytest.mark.asyncio
    @patch("src.security._carregar_config_keycloak")
    async def test_configuracao_incompleta(self, mock_carregar):
        mock_carregar.return_value = ("", "", "client-id", [])
        credenciais = MagicMock()
        credenciais.credentials = "fake-token"

        with pytest.raises(HTTPException) as exc:
            await obter_usuario_atual(credenciais)
        assert exc.value.status_code == 500

    @pytest.mark.asyncio
    @patch("src.security._obter_cliente_jwks")
    @patch("src.security._carregar_config_keycloak")
    async def test_token_expirado(self, mock_carregar, mock_jwks):
        mock_carregar.return_value = (
            "http://issuer",
            "http://jwks",
            "client-id",
            ["account"],
        )
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"
        mock_jwks.return_value.get_signing_key_from_jwt.return_value = mock_signing_key

        import jwt as jwt_lib
        credenciais = MagicMock()
        credenciais.credentials = "fake-token"

        with patch("src.security.jwt.decode", side_effect=jwt_lib.ExpiredSignatureError("expired")):
            with pytest.raises(HTTPException) as exc:
                await obter_usuario_atual(credenciais)
            assert exc.value.status_code == 401
            assert "expirou" in exc.value.detail

    @pytest.mark.asyncio
    @patch("src.security._obter_cliente_jwks")
    @patch("src.security._carregar_config_keycloak")
    async def test_token_invalido(self, mock_carregar, mock_jwks):
        mock_carregar.return_value = (
            "http://issuer",
            "http://jwks",
            "client-id",
            ["account"],
        )
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"
        mock_jwks.return_value.get_signing_key_from_jwt.return_value = mock_signing_key

        import jwt as jwt_lib
        credenciais = MagicMock()
        credenciais.credentials = "fake-token"

        with patch("src.security.jwt.decode", side_effect=jwt_lib.InvalidTokenError("invalid")):
            with pytest.raises(HTTPException) as exc:
                await obter_usuario_atual(credenciais)
            assert exc.value.status_code == 401

    @pytest.mark.asyncio
    @patch("src.security._obter_cliente_jwks")
    @patch("src.security._carregar_config_keycloak")
    async def test_jwks_client_error(self, mock_carregar, mock_jwks):
        from jwt import PyJWKClientError
        mock_carregar.return_value = (
            "http://issuer",
            "http://jwks",
            "client-id",
            ["account"],
        )
        mock_jwks.return_value.get_signing_key_from_jwt.side_effect = PyJWKClientError("jwks error")

        credenciais = MagicMock()
        credenciais.credentials = "fake-token"

        with pytest.raises(HTTPException) as exc:
            await obter_usuario_atual(credenciais)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    @patch("src.security._obter_cliente_jwks")
    @patch("src.security._carregar_config_keycloak")
    async def test_token_valido_sucesso(self, mock_carregar, mock_jwks):
        mock_carregar.return_value = (
            "http://issuer",
            "http://jwks",
            "client-id",
            ["account"],
        )
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"
        mock_jwks.return_value.get_signing_key_from_jwt.return_value = mock_signing_key

        payload = {"sub": "user-123", "azp": "client-id", "realm_access": {"roles": ["admin"]}}
        credenciais = MagicMock()
        credenciais.credentials = "fake-token"

        with patch("src.security.jwt.decode", return_value=payload):
            resultado = await obter_usuario_atual(credenciais)
            assert resultado["sub"] == "user-123"

    @pytest.mark.asyncio
    @patch("src.security._obter_cliente_jwks")
    @patch("src.security._carregar_config_keycloak")
    async def test_token_azp_invalido(self, mock_carregar, mock_jwks):
        mock_carregar.return_value = (
            "http://issuer",
            "http://jwks",
            "client-id",
            ["account"],
        )
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"
        mock_jwks.return_value.get_signing_key_from_jwt.return_value = mock_signing_key

        payload = {"sub": "user-123", "azp": "outro-client"}
        credenciais = MagicMock()
        credenciais.credentials = "fake-token"

        with patch("src.security.jwt.decode", return_value=payload):
            with pytest.raises(HTTPException) as exc:
                await obter_usuario_atual(credenciais)
            assert exc.value.status_code == 401
            assert "cliente" in exc.value.detail


class TestVerificarRoles:
    def test_role_permitida(self):
        dependencia = verificar_roles(["admin", "superadmin"])
        usuario = {"realm_access": {"roles": ["admin"]}}
        resultado = dependencia(usuario=usuario)
        assert resultado == usuario

    def test_role_negada(self):
        dependencia = verificar_roles(["superadmin"])
        usuario = {"realm_access": {"roles": ["viewer"]}}
        with pytest.raises(HTTPException) as exc:
            dependencia(usuario=usuario)
        assert exc.value.status_code == 403

    def test_sem_realm_access(self):
        dependencia = verificar_roles(["admin"])
        usuario = {}
        with pytest.raises(HTTPException) as exc:
            dependencia(usuario=usuario)
        assert exc.value.status_code == 403


class TestVerificarPermissaoSetor:
    def test_superadmin_acessa_qualquer_setor(self):
        from src.security import (
            verificar_permissao_setor,
            SETOR_EVENTOS,
            SETOR_PRODUTOS,
            SETOR_INSCRICOES,
        )
        usuario = {"realm_access": {"roles": ["admin", "superadmin"]}}
        assert verificar_permissao_setor(SETOR_EVENTOS)(usuario=usuario) == usuario
        assert verificar_permissao_setor(SETOR_PRODUTOS)(usuario=usuario) == usuario
        assert verificar_permissao_setor(SETOR_INSCRICOES)(usuario=usuario) == usuario

    def test_admin_setor_especifico_acessa_seu_setor(self):
        from src.security import verificar_permissao_setor, SETOR_EVENTOS, SETOR_PRODUTOS
        usuario_eventos = {"realm_access": {"roles": ["admin", "admin-eventos"]}}
        # Acesso permitido ao seu próprio setor
        assert verificar_permissao_setor(SETOR_EVENTOS)(usuario=usuario_eventos) == usuario_eventos

        # Acesso negado a outros setores
        with pytest.raises(HTTPException) as exc:
            verificar_permissao_setor(SETOR_PRODUTOS)(usuario=usuario_eventos)
        assert exc.value.status_code == 403
        assert "Acesso negado ao setor" in exc.value.detail

    def test_admin_dois_setores_acessa_ambos_mas_nao_terceiro(self):
        from src.security import (
            verificar_permissao_setor,
            SETOR_EVENTOS,
            SETOR_PRODUTOS,
            SETOR_INSCRICOES,
        )
        usuario_dois = {"realm_access": {"roles": ["admin", "admin-produtos", "admin-inscricoes"]}}
        assert verificar_permissao_setor(SETOR_PRODUTOS)(usuario=usuario_dois) == usuario_dois
        assert verificar_permissao_setor(SETOR_INSCRICOES)(usuario=usuario_dois) == usuario_dois

        with pytest.raises(HTTPException) as exc:
            verificar_permissao_setor(SETOR_EVENTOS)(usuario=usuario_dois)
        assert exc.value.status_code == 403

    def test_admin_legado_sem_papel_de_setor_mantem_acesso_geral(self):
        from src.security import verificar_permissao_setor, SETOR_EVENTOS, SETOR_PRODUTOS
        usuario_legado = {"realm_access": {"roles": ["admin"]}}
        assert verificar_permissao_setor(SETOR_EVENTOS)(usuario=usuario_legado) == usuario_legado
        assert verificar_permissao_setor(SETOR_PRODUTOS)(usuario=usuario_legado) == usuario_legado

    def test_usuario_sem_admin_tem_acesso_negado(self):
        from src.security import verificar_permissao_setor, SETOR_EVENTOS
        usuario_comum = {"realm_access": {"roles": ["viewer"]}}
        with pytest.raises(HTTPException) as exc:
            verificar_permissao_setor(SETOR_EVENTOS)(usuario=usuario_comum)
        assert exc.value.status_code == 403

    def test_papel_de_setor_sem_papel_admin_negado(self):
        from src.security import verificar_permissao_setor, SETOR_EVENTOS
        usuario_invalido = {"realm_access": {"roles": ["admin-eventos"]}}
        with pytest.raises(HTTPException) as exc:
            verificar_permissao_setor(SETOR_EVENTOS)(usuario=usuario_invalido)
        assert exc.value.status_code == 403
