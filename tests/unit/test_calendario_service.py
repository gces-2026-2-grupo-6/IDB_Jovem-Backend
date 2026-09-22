import json
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from src.calendario.schema import RespostaEvento, SolicitacaoEvento
from src.calendario.service import ServicoCalendario


def _http_error(codigo: int, msg: str = "erro") -> HTTPError:
    """HTTPError com `hdrs` tipado para satisfazer o type checker."""
    from email.message import Message
    return HTTPError(url="x", code=codigo, msg=msg, hdrs=Message(), fp=None)

@pytest.fixture
def servico_sem_token():
    """ServicoCalendario sem GOOGLE_REFRESH_TOKEN — força caminho de mock."""
    with patch.dict("os.environ", {}, clear=False):
        servico = ServicoCalendario()
        servico.refresh_token = None
        return servico


@pytest.fixture
def servico_com_token():
    """ServicoCalendario com refresh_token e ServicoAuth mockado."""
    servico = ServicoCalendario()
    servico.refresh_token = "refresh-token-fake"
    credenciais_fake = MagicMock()
    credenciais_fake.token = "access-token-fake"
    servico.servico_auth = MagicMock()
    servico.servico_auth.obter_credenciais_validas.return_value = credenciais_fake
    return servico

SOLICITACAO_EVENTO = SolicitacaoEvento(
    nome="Retiro Teen 2025",
    data=date(2025, 7, 10),
    local="Auditório Principal",
    descricao="Evento anual",
    data_inicio=datetime(2025, 7, 10, 8, 0, tzinfo=timezone.utc),
    data_fim=datetime(2025, 7, 12, 18, 0, tzinfo=timezone.utc),
)


def _resposta_urlopen(payload: dict):
    """Constroi um context-manager fake imitando o retorno de urlopen."""
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
    cm.__exit__.return_value = False
    return cm

class TestObterTokenValido:

    def test_sem_refresh_token_retorna_none(self, servico_sem_token):
        assert servico_sem_token._obter_token_valido() is None

    def test_com_refresh_token_retorna_access_token(self, servico_com_token):
        assert servico_com_token._obter_token_valido() == "access-token-fake"

    def test_falha_em_renovar_converte_para_runtimeerror(self, servico_com_token):
        servico_com_token.servico_auth.obter_credenciais_validas.side_effect = Exception("boom")
        with pytest.raises(RuntimeError, match="Falha automática ao renovar credenciais"):
            servico_com_token._obter_token_valido()

class TestListarEvento:

    def test_sem_token_retorna_mocks(self, servico_sem_token):
        eventos = servico_sem_token.listar_evento()
        assert len(eventos) == 3
        assert all(isinstance(e, RespostaEvento) for e in eventos)
        assert all(e.nome.startswith("[MOCK]") for e in eventos)

    def test_sem_token_eventos_em_2026(self, servico_sem_token):
        eventos = servico_sem_token.listar_evento()
        assert all(e.data_inicio.year == 2026 for e in eventos)

    def test_com_token_erro_de_rede_converte_para_runtimeerror(self, servico_com_token):
        with patch("src.calendario.service.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = URLError("sem internet")
            with pytest.raises(RuntimeError, match="Falha ao acessar Google Calendar"):
                servico_com_token.listar_evento()

    def test_com_token_http_error_converte_para_runtimeerror(self, servico_com_token):
        with patch("src.calendario.service.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = _http_error(500)
            with pytest.raises(RuntimeError, match="Falha ao acessar Google Calendar"):
                servico_com_token.listar_evento()

    def test_com_token_resposta_vazia_retorna_lista_vazia(self, servico_com_token):
        with patch("src.calendario.service.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _resposta_urlopen({"items": []})
            assert servico_com_token.listar_evento() == []

    def test_com_token_converte_itens_e_descarta_os_sem_data(self, servico_com_token):
        """Substitui um teste antigo que chamava o metodo sem nenhum assert."""
        itens = [
            {"id": "a1", "summary": "Retiro", "start": {"date": "2026-06-10"}},
            {"id": "a2", "summary": "Sem data", "start": {}},
        ]
        with patch("src.calendario.service.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _resposta_urlopen({"items": itens})
            eventos = servico_com_token.listar_evento()
        assert [e.nome for e in eventos] == ["Retiro"]

class TestParsearData:

    def test_data_simples(self, servico_sem_token):
        assert servico_sem_token._parsear_data(
            {"start": {"date": "2025-07-10"}}
        , "start") == date(2025, 7, 10)

    def test_data_com_horario_z(self, servico_sem_token):
        assert servico_sem_token._parsear_data(
            {"start": {"dateTime": "2025-07-10T08:00:00Z"}}
        , "start") == date(2025, 7, 10)

    def test_data_com_horario_offset(self, servico_sem_token):
        assert servico_sem_token._parsear_data(
            {"start": {"dateTime": "2025-07-10T08:00:00+00:00"}}
        , "start") == date(2025, 7, 10)

    def test_sem_start_retorna_none(self, servico_sem_token):
        assert servico_sem_token._parsear_data({}, "start") is None

    def test_start_vazio_retorna_none(self, servico_sem_token):
        assert servico_sem_token._parsear_data({"start": {}}, "start") is None


class TestConverterEvento:

    def test_evento_valido(self, servico_sem_token):
        registro = {
            "summary": "Festa Junina",
            "location": "Pátio",
            "start": {"date": "2025-06-20"},
        }
        resultado = servico_sem_token._converter_evento(registro)
        assert resultado is not None
        assert resultado.nome == "Festa Junina"
        assert resultado.local == "Pátio"
        assert resultado.data_inicio == date(2025, 6, 20)

    def test_evento_sem_data_retorna_none(self, servico_sem_token):
        assert servico_sem_token._converter_evento({"summary": "X"}) is None

    def test_evento_sem_summary_usa_padrao(self, servico_sem_token):
        registro = {"start": {"date": "2025-06-20"}}
        resultado = servico_sem_token._converter_evento(registro)
        assert resultado.nome == "(Sem nome)"
        assert resultado.local == ""

class TestCriarEvento:

    def test_sem_token_retorna_none(self, servico_sem_token):
        assert servico_sem_token.criar_evento(SOLICITACAO_EVENTO, "Pátio") is None

    def test_com_token_envia_post_e_retorna_id(self, servico_com_token):
        with patch("src.calendario.service.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _resposta_urlopen({"id": "evento-google-abc"})
            id_criado = servico_com_token.criar_evento(SOLICITACAO_EVENTO, "Pátio")
        assert id_criado == "evento-google-abc"

    def test_com_token_envia_payload_correto(self, servico_com_token):
        with patch("src.calendario.service.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _resposta_urlopen({"id": "x"})
            servico_com_token.criar_evento(SOLICITACAO_EVENTO, "Auditório")
            requisicao = mock_urlopen.call_args.args[0]
            corpo = json.loads(requisicao.data.decode("utf-8"))
            assert requisicao.get_method() == "POST"
            assert corpo["summary"] == SOLICITACAO_EVENTO.nome
            assert corpo["location"] == "Auditório"
            assert corpo["description"] == SOLICITACAO_EVENTO.descricao
            assert corpo["start"]["dateTime"] == SOLICITACAO_EVENTO.data_inicio.isoformat()
            assert corpo["end"]["dateTime"] == SOLICITACAO_EVENTO.data_fim.isoformat()

class TestAtualizarEvento:

    def test_sem_token_retorna_silenciosamente(self, servico_sem_token):
        assert servico_sem_token.atualizar_evento("id-x", SOLICITACAO_EVENTO, "Pátio") is None

    def test_com_token_envia_patch(self, servico_com_token):
        with patch("src.calendario.service.urlopen") as mock_urlopen:
            servico_com_token.atualizar_evento("id-x", SOLICITACAO_EVENTO, "Auditório")
            requisicao = mock_urlopen.call_args.args[0]
            assert requisicao.get_method() == "PATCH"
            assert "events/id-x" in requisicao.full_url

    def test_http_410_e_ignorado(self, servico_com_token):
        with patch("src.calendario.service.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = _http_error(410, "gone")
            assert servico_com_token.atualizar_evento("id-x", SOLICITACAO_EVENTO, "Pátio") is None

    @pytest.mark.parametrize("codigo", [400, 401, 403, 404, 500])
    def test_outros_http_errors_disparam_runtimeerror(self, servico_com_token, codigo):
        with patch("src.calendario.service.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = _http_error(codigo)
            with pytest.raises(RuntimeError, match="Falha ao atualizar evento"):
                servico_com_token.atualizar_evento("id-x", SOLICITACAO_EVENTO, "Pátio")

    def test_url_error_dispara_runtimeerror(self, servico_com_token):
        with patch("src.calendario.service.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = URLError("sem rede")
            with pytest.raises(RuntimeError, match="Falha ao conectar"):
                servico_com_token.atualizar_evento("id-x", SOLICITACAO_EVENTO, "Pátio")

class TestDeletarEvento:

    def test_sem_token_retorna_silenciosamente(self, servico_sem_token):
        assert servico_sem_token.deletar_evento("id-x") is None

    def test_com_token_envia_delete(self, servico_com_token):
        with patch("src.calendario.service.urlopen") as mock_urlopen:
            servico_com_token.deletar_evento("id-abc")
            requisicao = mock_urlopen.call_args.args[0]
            assert requisicao.get_method() == "DELETE"
            assert "events/id-abc" in requisicao.full_url

    def test_http_410_e_ignorado(self, servico_com_token):
        with patch("src.calendario.service.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = _http_error(410, "gone")
            assert servico_com_token.deletar_evento("id-x") is None

    @pytest.mark.parametrize("codigo", [400, 401, 403, 404, 500])
    def test_outros_http_errors_disparam_runtimeerror(self, servico_com_token, codigo):
        with patch("src.calendario.service.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = _http_error(codigo)
            with pytest.raises(RuntimeError, match="Falha ao deletar evento"):
                servico_com_token.deletar_evento("id-x")

    def test_url_error_dispara_runtimeerror(self, servico_com_token):
        with patch("src.calendario.service.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = URLError("sem rede")
            with pytest.raises(RuntimeError, match="Falha ao conectar"):
                servico_com_token.deletar_evento("id-x")
