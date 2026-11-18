"""Emissor de tokens para os testes de endpoint.

Os testes de endpoint falam por HTTP com a aplicacao rodando em container,
contra o Postgres de verdade. Ate aqui eles so alcancavam rota publica: sem
Keycloak no job, nao havia como obter token, e todo o caminho de escrita —
onde o dado e gravado no Postgres e relido — ficava de fora.

Este modulo resolve isso sem subir Keycloak. A aplicacao valida o token
contra o JWKS que a configuracao apontar; entao o proprio teste gera um par
de chaves, publica a chave publica num servidor HTTP local e assina os
tokens com a privada. Do ponto de vista da aplicacao, e um emissor OpenID
como qualquer outro: a validacao de assinatura, emissor, audiencia e `azp`
roda inteira, sem nenhum desvio no codigo de producao.

A chave e gerada a cada execucao e nunca sai da memoria — nao ha segredo no
repositorio.

Para os testes autenticados rodarem, a aplicacao precisa ter subido com:

    KEYCLOAK_ISSUER=http://localhost:8765/realms/endpoint
    KEYCLOAK_JWKS_URL=http://localhost:8765/jwks
    KEYCLOAK_CLIENT_ID=jovem-endpoint

E o que o job de endpoint do CI faz. Fora do CI, se a aplicacao estiver
apontando para outro emissor (um Keycloak de verdade, por exemplo), os
testes autenticados se declaram inconclusivos com esta instrucao. No CI eles
falham: pular em silencio la seria ficar verde por ausencia.
"""

import base64
import json
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

BASE_URL = "http://localhost:8000"

PORTA_EMISSOR = 8765
EMISSOR = f"http://localhost:{PORTA_EMISSOR}/realms/endpoint"
CLIENT_ID = "jovem-endpoint"


def _b64(numero: int) -> str:
    bruto = numero.to_bytes((numero.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(bruto).rstrip(b"=").decode()


class EmissorDeTokens:
    """Par de chaves em memoria, JWKS publicado e fabrica de tokens."""

    def __init__(self):
        self._chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        # `kid` novo a cada execucao: a aplicacao guarda o JWKS em cache, e e
        # o `kid` desconhecido que a faz buscar o conjunto de chaves de novo.
        self._kid = uuid.uuid4().hex
        publicos = self._chave.public_key().public_numbers()
        self.jwks = {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "alg": "RS256",
                    "kid": self._kid,
                    "n": _b64(publicos.n),
                    "e": _b64(publicos.e),
                }
            ]
        }

    def token(self, papeis: list[str]) -> str:
        agora = int(time.time())
        return jwt.encode(
            {
                "iss": EMISSOR,
                "aud": "account",
                "azp": CLIENT_ID,
                "sub": "usuario-de-endpoint",
                "iat": agora,
                "exp": agora + 600,
                "realm_access": {"roles": papeis},
            },
            self._chave,
            algorithm="RS256",
            headers={"kid": self._kid},
        )


@pytest.fixture(scope="session")
def emissor():
    emissor_de_tokens = EmissorDeTokens()
    corpo = json.dumps(emissor_de_tokens.jwks).encode()

    class Manipulador(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - assinatura da biblioteca padrao
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *_):
            """Silencio: o log padrao polui a saida do pytest."""

    servidor = ThreadingHTTPServer(("0.0.0.0", PORTA_EMISSOR), Manipulador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        yield emissor_de_tokens
    finally:
        servidor.shutdown()


def _cliente(emissor, papeis):
    return httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {emissor.token(papeis)}"},
        timeout=30,
    )


@pytest.fixture(scope="session")
def superadmin(emissor):
    """Cliente HTTP autenticado como superadministradora.

    Antes de entregar o cliente, confere que a aplicacao aceita o emissor de
    teste. Sem essa conferencia, uma aplicacao apontando para outro Keycloak
    faria todos os testes autenticados falharem com 401 — mensagem que manda
    procurar defeito no lugar errado.
    """
    cliente = _cliente(emissor, ["superadmin"])
    sonda = cliente.get("/painel/links")
    if sonda.status_code != 200:
        motivo = (
            f"a aplicacao recusou o token do emissor de teste ({sonda.status_code}). "
            f"Suba-a com KEYCLOAK_ISSUER={EMISSOR}, "
            f"KEYCLOAK_JWKS_URL=http://localhost:{PORTA_EMISSOR}/jwks e "
            f"KEYCLOAK_CLIENT_ID={CLIENT_ID}."
        )
        cliente.close()
        if os.environ.get("CI"):
            pytest.fail(motivo)
        pytest.skip(motivo)
    try:
        yield cliente
    finally:
        cliente.close()


@pytest.fixture(scope="session")
def admin_sem_setor(emissor, superadmin):
    """Administrador comum, sem papel de setor (depende da sonda acima)."""
    with _cliente(emissor, ["admin"]) as cliente:
        yield cliente


@pytest.fixture(scope="session")
def anonimo():
    with httpx.Client(base_url=BASE_URL, timeout=30) as cliente:
        yield cliente
