"""Modulo de seguranca para integracao e validacao de tokens JWT do Keycloak."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient, PyJWKClientError

from src.config import configuracoes

autenticacao_bearer = HTTPBearer()

_JWKS_CLIENT: PyJWKClient | None = None
_JWKS_URL: str | None = None


def _parse_audiences(valor: str, client_id: str) -> list[str]:
    audiencia: list[str] = []
    if valor:
        audiencia = [item.strip() for item in valor.split(",") if item.strip()]
    if client_id and client_id not in audiencia:
        audiencia.append(client_id)
    if "account" not in audiencia:
        audiencia.append("account")
    return audiencia


def _carregar_config_keycloak() -> tuple[str, str, str, list[str]]:
    base_url = configuracoes.KEYCLOAK_URL.rstrip("/")
    realm = configuracoes.KEYCLOAK_REALM
    client_id = configuracoes.KEYCLOAK_CLIENT_ID

    issuer = configuracoes.KEYCLOAK_ISSUER
    if not issuer and base_url and realm:
        issuer = f"{base_url}/realms/{realm}"

    jwks_url = configuracoes.KEYCLOAK_JWKS_URL
    if not jwks_url and issuer:
        jwks_url = f"{issuer}/protocol/openid-connect/certs"

    audiencia = _parse_audiences(configuracoes.KEYCLOAK_AUDIENCE, client_id)
    return issuer, jwks_url, client_id, audiencia


def _obter_cliente_jwks(jwks_url: str) -> PyJWKClient:
    global _JWKS_CLIENT, _JWKS_URL
    if _JWKS_CLIENT is None or _JWKS_URL != jwks_url:
        _JWKS_CLIENT = PyJWKClient(jwks_url)
        _JWKS_URL = jwks_url
    return _JWKS_CLIENT


async def obter_usuario_atual(
    credenciais: HTTPAuthorizationCredentials = Depends(autenticacao_bearer)
):
    """Decodifica o token JWT enviado pelo front-end e valida as permissoes."""
    token = credenciais.credentials
    issuer, jwks_url, client_id, audiencia = _carregar_config_keycloak()
    if not issuer or not jwks_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuracao do Keycloak incompleta.",
        )

    try:
        jwks_client = _obter_cliente_jwks(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token).key
        decode_args = {
            "key": signing_key,
            "algorithms": ["RS256"],
            "options": {"verify_aud": bool(audiencia), "verify_iss": True},
            "issuer": issuer,
        }
        if audiencia:
            decode_args["audience"] = audiencia
        payload_token = jwt.decode(token, **decode_args)

        if client_id and payload_token.get("azp") != client_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalido para este cliente.",
            )
        return payload_token
    except jwt.ExpiredSignatureError as erro:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="O token de acesso expirou."
        ) from erro
    except jwt.InvalidTokenError as erro:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido ou assinatura incorreta."
        ) from erro
    except PyJWKClientError as erro:
        print("ERRO JWKS:", repr(erro))
        print("JWKS URL:", jwks_url)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Falha ao validar o token do Keycloak: {erro}",
        ) from erro

def verificar_roles(roles_exigidas: list[str]):
    """Fabrica de dependencias para verificar multiplos papeis."""
    def dependencia(usuario: dict = Depends(obter_usuario_atual)):
        acesso_realm = usuario.get("realm_access", {})
        roles_usuario = acesso_realm.get("roles", [])

        # O campo precisa ser uma colecao de papeis. Quando vem como string,
        # o operador "in" passaria a comparar substrings e "admin" seria
        # aceito por casar dentro de "superadmin".
        if not isinstance(roles_usuario, (list, tuple, set)):
            roles_usuario = []

        if not any(role in roles_usuario for role in roles_exigidas):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Acesso negado. Requer um dos papeis: "
                    f"{', '.join(roles_exigidas)}"
                ),
            )
        return usuario

    return dependencia


SETOR_EVENTOS = "eventos"
SETOR_PRODUTOS = "produtos"
SETOR_INSCRICOES = "inscricoes"

PAPEL_DO_SETOR = {
    SETOR_EVENTOS: "admin-eventos",
    SETOR_PRODUTOS: "admin-produtos",
    SETOR_INSCRICOES: "admin-inscricoes",
}

TODOS_PAPEIS_SETORES = set(PAPEL_DO_SETOR.values())


def verificar_permissao_setor(setor_alvo: str):
    """
    Fabrica de dependencias para verificar permissao de administrador por setor (US03 / RF01).
    - superadmin: acesso total a todos os setores.
    - admin:
        - Se possuir papeis especificos de setor, exige o papel correspondente ao setor alvo.
        - Se nao possuir nenhum papel especifico de setor, mantem acesso geral (retrocompatibilidade).
    - Outros: HTTP 403 Forbidden.
    """
    papel_esperado = PAPEL_DO_SETOR.get(setor_alvo)

    def dependencia(usuario: dict = Depends(obter_usuario_atual)):
        acesso_realm = usuario.get("realm_access", {})
        roles_usuario = set(acesso_realm.get("roles", []))

        if "superadmin" in roles_usuario:
            return usuario

        if "admin" not in roles_usuario:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado. Requer permissão de administrador para o setor '{setor_alvo}'.",
            )

        papeis_de_setor = roles_usuario.intersection(TODOS_PAPEIS_SETORES)
        if papeis_de_setor and papel_esperado not in roles_usuario:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado ao setor '{setor_alvo}'. Requer o papel '{papel_esperado}' ou superadmin.",
            )

        return usuario

    return dependencia

