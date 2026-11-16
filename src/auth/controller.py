import os
import stat
import tempfile

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from src.auth.service import ServicoAuth

router = APIRouter(prefix="/auth", tags=["Autenticação (OAuth2 Google)"])

# Onde o refresh token é depositado para quem está configurando o servidor.
# Ver _guardar_refresh_token.
ARQUIVO_REFRESH_TOKEN = os.path.join(tempfile.gettempdir(), "refresh_token_google.txt")


def _guardar_refresh_token(token: str) -> None:
    """Deposita o refresh token num arquivo só legível pelo dono do processo.

    O refresh token é credencial de longa duração da conta Google do projeto
    (Drive, Calendar e Forms): o access_token expira em uma hora, este não
    expira sozinho. Quem o obtiver fala com a conta até alguém revogar — e
    ninguém revoga, porque não há sinal de que vazou.

    Por isso ele não volta no corpo da resposta nem vai para o stdout:

    - a resposta é de uma rota GET, cuja URL já circula por histórico de
      navegador, log de proxy e cabeçalho Referer;
    - o stdout, em produção, é o log do contêiner: `docker compose logs`
      mostraria a credencial em texto puro, e o log sobrevive ao contêiner.

    Quem está configurando o servidor lê o arquivo uma vez, copia para a
    variável de ambiente e apaga:

        docker compose -f docker-compose.prod.yml exec jovem-backend \\
            cat /tmp/refresh_token_google.txt
    """
    with open(ARQUIVO_REFRESH_TOKEN, "w", encoding="utf-8") as arquivo:
        arquivo.write(token)
    os.chmod(ARQUIVO_REFRESH_TOKEN, stat.S_IRUSR | stat.S_IWUSR)

@router.get("/login")
def iniciar_login(request: Request):
    """
    Chame esta rota no navegador para iniciar o login do Admin.
    Ela redirecionará você direto para o Google.
    """
    servico = ServicoAuth()
    url_google, estado, verificador_codigo = servico.gerar_url_login()
    request.session["google_estado"] = estado
    request.session["google_verificador_codigo"] = verificador_codigo
    return RedirectResponse(url=url_google)


@router.get("/callback")
def callback_google(request: Request, codigo: str = Query(..., alias="code")):
    """
    O Google redireciona para cá automaticamente enviando o '?code=...'
    """
    estado = request.session.get("google_estado")
    verificador_codigo = request.session.get("google_verificador_codigo")
    if not estado or not verificador_codigo:
        raise HTTPException(status_code=400, detail="Sessao OAuth expirada. Refaça o login.")

    repositorio = ServicoAuth()
    tokens_google = repositorio.trocar_codigo_por_tokens(codigo, estado, verificador_codigo)

    request.session.pop("google_estado", None)
    request.session.pop("google_verificador_codigo", None)

    refresh_token = tokens_google.get("refresh_token")
    if refresh_token:
        _guardar_refresh_token(refresh_token)
        instrucoes = (
            "O refresh token foi gravado dentro do contêiner, fora desta "
            f"resposta e fora do log. Leia-o uma vez com: docker compose "
            f"-f docker-compose.prod.yml exec jovem-backend cat "
            f"{ARQUIVO_REFRESH_TOKEN} — copie para GOOGLE_REFRESH_TOKEN no "
            ".env e apague o arquivo em seguida."
        )
    else:
        # O Google só devolve refresh_token no primeiro consentimento. Sem
        # prompt=consent, uma segunda autorização volta sem ele — e o
        # silêncio aqui já custou tempo de quem configurou o servidor.
        instrucoes = (
            "O Google não devolveu refresh token nesta autorização: ele só "
            "vem no primeiro consentimento. Para obter outro, revogue o "
            "acesso do aplicativo na conta Google e refaça o login."
        )

    return {
        "mensagem": "Admin autenticado com sucesso no Google!",
        "instrucoes": instrucoes,
        "recebeu_refresh_token": bool(refresh_token),
    }
