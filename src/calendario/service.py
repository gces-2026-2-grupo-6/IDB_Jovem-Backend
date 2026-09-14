import os
from datetime import date, datetime, timezone
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.calendario.schema import RespostaEvento, SolicitacaoEvento
from src.auth.service import ServicoAuth  

class ServicoCalendario:
    def __init__(self):
        self.refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
        self.servico_auth = ServicoAuth()

    def _obter_token_valido(self) -> str | None:
        """
        Substitui o antigo _extrair_token.
        Busca o refresh_token do .env, renova no Google se necessário e retorna o access_token ativo.
        """
        if not self.refresh_token:
            return None

        try:
            credenciais = self.servico_auth.obter_credenciais_validas(self.refresh_token)
            return credenciais.token
        except Exception as erro:
            raise RuntimeError("Falha automática ao renovar credenciais do Google") from erro

    def _montar_url_evento(self) -> str:
        parametros = {
            "timeMin": datetime.now(timezone.utc).isoformat(),
            "maxResults": 10,
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        return (
            "https://www.googleapis.com/calendar/v3/calendars/primary/events?"
            f"{urlencode(parametros)}"
        )

    def _parsear_data(self, registro: dict, chave: str) -> date | None:
        campo = registro.get(chave, {})
        data_texto = campo.get("date") or campo.get("dateTime")
        if not data_texto:
            return None
        if "T" in data_texto:
            data_texto = data_texto.replace("Z", "+00:00")
            return datetime.fromisoformat(data_texto).date()
        return date.fromisoformat(data_texto)

    def _converter_evento(self, registro: dict) -> RespostaEvento | None:
        data_inicio = self._parsear_data(registro, "start")
        if not data_inicio:
            return None
        data_fim = self._parsear_data(registro, "end")
        return RespostaEvento(
            nome=registro.get("summary", "(Sem nome)"),
            data_inicio=data_inicio,
            data_fim=data_fim,
            local=registro.get("location", ""),
        )

    def _buscar_evento_google(self, token: str) -> list[RespostaEvento]:
        url = self._montar_url_evento()
        requisicao = Request(url)
        requisicao.add_header("Authorization", f"Bearer {token}")
        requisicao.add_header("Accept", "application/json")
        try:
            with urlopen(requisicao, timeout=10) as resposta:
                corpo = resposta.read().decode("utf-8")
        except (HTTPError, URLError) as erro:
            raise RuntimeError("Falha ao acessar Google Calendar") from erro

        dados = json.loads(corpo)
        itens = dados.get("items", [])
        eventos: list[RespostaEvento] = []
        for registro in itens:
            evento = self._converter_evento(registro)
            if evento:
                eventos.append(evento)
        return eventos

    def listar_evento(self) -> list[RespostaEvento]:
        """
        Busca os eventos reais do Google usando o Refresh Token automático.
        """
        token = self._obter_token_valido()

        if not token:
            return [
                RespostaEvento(
                    nome="[MOCK] Boas-vindas aos Novos Voluntarios",
                    data_inicio=date(2026, 6, 5),
                    data_fim=date(2026, 6, 5),
                    local="Auditório Principal"
                ),
                RespostaEvento(
                    nome="[MOCK] Alinhamento do Projeto com Cliente",
                    data_inicio=date(2026, 6, 12),
                    data_fim=date(2026, 6, 12),
                    local="Sala de Reuniões 02"
                ),
                RespostaEvento(
                    nome="[MOCK] Mutirao de Cadastro",
                    data_inicio=date(2026, 6, 20),
                    data_fim=date(2026, 6, 20),
                    local="Comunidade Solar"
                )
            ]

        return self._buscar_evento_google(token)

    def criar_evento(self, evento: SolicitacaoEvento, nome_local: str) -> str:
        token = self._obter_token_valido()

        if not token:
            return None

        url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

        corpo = {
            "summary": evento.nome,
            "location": nome_local,
            "description": evento.descricao,
            "start": {"dateTime": (evento.data_inicio.isoformat())},
            "end": {"dateTime": (evento.data_fim.isoformat())}
        }

        requisicao = Request(url, data=json.dumps(corpo).encode("utf-8"), method="POST")
        requisicao.add_header("Authorization", f"Bearer {token}")
        requisicao.add_header("Content-Type", "application/json")

        with urlopen(requisicao, timeout=10) as resposta:

            corpo_resposta = (resposta.read().decode("utf-8"))

        dados = json.loads(corpo_resposta)

        return dados.get("id")

    def atualizar_evento(self, calendario_event_id, evento: SolicitacaoEvento, nome_local: str) -> str:
        token = self._obter_token_valido()

        if not token:
            return

        url = (
            "https://www.googleapis.com/calendar/v3/"
            f"calendars/primary/events/{calendario_event_id}"
        )

        corpo = {
            "summary": evento.nome,
            "location": nome_local,
            "description": evento.descricao,
            "start": {"dateTime": evento.data_inicio.isoformat()},
            "end": {"dateTime": evento.data_fim.isoformat()}
        }

        requisicao = Request(url, data=json.dumps(corpo).encode("utf-8"), method="PATCH")
        requisicao.add_header("Authorization", f"Bearer {token}")
        requisicao.add_header("Content-Type", "application/json")
        try:
            urlopen(requisicao, timeout=10)

        except HTTPError as erro:

            if erro.code == 410:

                return
            raise RuntimeError("Falha ao atualizar evento no Google Calendar") from erro
        except URLError as erro:
            raise RuntimeError("Falha ao conectar no Google Calendar") from erro

    def deletar_evento(self, calendario_event_id):
        token = self._obter_token_valido()

        if not token:
            return

        url = (
            "https://www.googleapis.com/calendar/v3/"
            f"calendars/primary/events/{calendario_event_id}"
        )

        requisicao = Request(url, method="DELETE")
        requisicao.add_header("Authorization", f"Bearer {token}")
        try:
            urlopen(requisicao, timeout=10)

        except HTTPError as erro:

            if erro.code == 410:

                return
            raise RuntimeError("Falha ao deletar evento no Google Calendar") from erro
        except URLError as erro:
            raise RuntimeError("Falha ao conectar no Google Calendar") from erro
