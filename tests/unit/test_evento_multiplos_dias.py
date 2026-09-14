"""
Testes de regressao para eventos de multiplos dias.

Cobre as historias US01 (evento em multiplos dias, inclusive nao consecutivos)
e US02 (informacoes completas do evento) do Backlog de Melhorias.

Contexto da elicitacao: a cliente relatou que "hoje no cadastro so e possivel
colocar evento de 1 dia". A analise do codigo mostrou que o modelo ja suporta
data_inicio e data_fim distintas — o que faltava era garantia de que faixas
longas e nao consecutivas sejam aceitas e preservadas.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.evento.model import Evento
from src.evento.schema import SolicitacaoEvento, TipoEvento
from src.evento.service import ServicoEvento
from src.shared.utils import validar_datas

BRASILIA_LAT = -15.7942
BRASILIA_LON = -47.8822


@pytest.fixture
def mock_repositorio():
    return MagicMock()


@pytest.fixture
def mock_calendario():
    calendario = MagicMock()
    calendario.criar_evento.return_value = "cal-id-123"
    return calendario


@pytest.fixture
def mock_mapa():
    mapa = MagicMock()
    mapa.buscar_endereco_por_coordenadas.return_value = "Endereco Teste"
    return mapa


@pytest.fixture
def servico(mock_repositorio, mock_calendario, mock_mapa):
    return ServicoEvento(
        repositorio=mock_repositorio,
        google_calendario=mock_calendario,
        mapa_servico=mock_mapa,
    )


def montar_solicitacao(data_inicio, data_fim, **extras):
    """Monta uma solicitacao valida, permitindo sobrescrever campos."""
    dados = {
        "nome": "Acampamento de Teste",
        "tipo_evento": TipoEvento.ACAMPAMENTO,
        "descricao": "Evento usado nos testes de multiplos dias",
        "local_latitude": BRASILIA_LAT,
        "local_longitude": BRASILIA_LON,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }
    dados.update(extras)
    return SolicitacaoEvento(**dados)


class TestValidacaoDeFaixaDeDatas:
    """A validacao de datas nao pode restringir a duracao do evento."""

    def test_aceita_evento_de_um_unico_dia(self):
        inicio = datetime(2026, 10, 10, 9, 0)
        fim = datetime(2026, 10, 10, 18, 0)
        assert validar_datas(inicio, fim) is None

    def test_aceita_acampamento_de_tres_dias(self):
        """US01 — caso citado pela cliente: acampamento de 3 dias."""
        inicio = datetime(2026, 10, 10, 9, 0)
        fim = datetime(2026, 10, 12, 18, 0)
        assert validar_datas(inicio, fim) is None

    def test_aceita_dias_nao_consecutivos(self):
        """US01 — a cliente confirmou que dias nao consecutivos devem ser aceitos."""
        inicio = datetime(2026, 10, 3, 9, 0)
        fim = datetime(2026, 10, 17, 18, 0)
        assert validar_datas(inicio, fim) is None

    def test_aceita_evento_que_cruza_a_virada_do_mes(self):
        inicio = datetime(2026, 10, 30, 20, 0)
        fim = datetime(2026, 11, 2, 8, 0)
        assert validar_datas(inicio, fim) is None

    def test_aceita_evento_que_cruza_a_virada_do_ano(self):
        inicio = datetime(2026, 12, 30, 20, 0)
        fim = datetime(2027, 1, 2, 8, 0)
        assert validar_datas(inicio, fim) is None

    def test_rejeita_termino_anterior_ao_inicio(self):
        inicio = datetime(2026, 10, 12, 9, 0)
        fim = datetime(2026, 10, 10, 18, 0)
        with pytest.raises(ValueError, match="maior que o valor inicial"):
            validar_datas(inicio, fim)

    def test_rejeita_inicio_igual_ao_termino(self):
        momento = datetime(2026, 10, 10, 9, 0)
        with pytest.raises(ValueError, match="maior que o valor inicial"):
            validar_datas(momento, momento)


class TestCriacaoDeEventoMultiplosDias:
    """A faixa de datas informada precisa chegar intacta ao repositorio."""

    def test_preserva_faixa_de_tres_dias_ao_salvar(self, servico, mock_repositorio):
        """US01 — a duracao nao pode ser truncada para um unico dia."""
        inicio = datetime.now() + timedelta(days=30)
        fim = inicio + timedelta(days=2, hours=9)
        dados = montar_solicitacao(inicio, fim)

        evento_salvo = Evento(**dados.model_dump())
        evento_salvo.evento_id = 1
        mock_repositorio.salvar.return_value = evento_salvo

        resultado = servico.criar_evento(dados)

        assert resultado.data_inicio == inicio
        assert resultado.data_fim == fim
        assert (resultado.data_fim - resultado.data_inicio).days == 2

    def test_preserva_faixa_de_dias_nao_consecutivos(self, servico, mock_repositorio):
        """US01 — tres sabados seguidos: 14 dias entre inicio e fim."""
        inicio = datetime.now() + timedelta(days=30)
        fim = inicio + timedelta(days=14, hours=9)
        dados = montar_solicitacao(inicio, fim)

        evento_salvo = Evento(**dados.model_dump())
        evento_salvo.evento_id = 1
        mock_repositorio.salvar.return_value = evento_salvo

        resultado = servico.criar_evento(dados)

        assert (resultado.data_fim - resultado.data_inicio).days == 14

    def test_sincroniza_faixa_completa_com_o_calendario(
        self, servico, mock_repositorio, mock_calendario
    ):
        """O evento no Google Calendar deve refletir todos os dias, nao so o primeiro."""
        inicio = datetime.now() + timedelta(days=30)
        fim = inicio + timedelta(days=2, hours=9)
        dados = montar_solicitacao(inicio, fim)

        evento_salvo = Evento(**dados.model_dump())
        evento_salvo.evento_id = 1
        mock_repositorio.salvar.return_value = evento_salvo

        servico.criar_evento(dados)

        mock_calendario.criar_evento.assert_called_once()
        evento_enviado = mock_calendario.criar_evento.call_args[0][0]
        assert evento_enviado.data_fim == fim

    def test_rejeita_criacao_com_datas_invertidas(self, servico, mock_repositorio):
        inicio = datetime.now() + timedelta(days=30)
        fim = inicio - timedelta(days=1)
        dados = montar_solicitacao(inicio, fim)

        with pytest.raises(ValueError, match="maior que o valor inicial"):
            servico.criar_evento(dados)

        mock_repositorio.salvar.assert_not_called()

    def test_nao_sincroniza_calendario_quando_datas_sao_invalidas(
        self, servico, mock_calendario
    ):
        """Evento invalido nao pode vazar para o Google Calendar."""
        inicio = datetime.now() + timedelta(days=30)
        dados = montar_solicitacao(inicio, inicio - timedelta(hours=1))

        with pytest.raises(ValueError):
            servico.criar_evento(dados)

        mock_calendario.criar_evento.assert_not_called()


class TestCamposComplementaresDoEvento:
    """US02 — campos que a cliente marcou como faltantes no cadastro."""

    def test_aceita_link_de_formulario_de_inscricao(self, servico, mock_repositorio):
        inicio = datetime.now() + timedelta(days=30)
        fim = inicio + timedelta(days=2)
        dados = montar_solicitacao(
            inicio, fim, formulario_link="https://forms.gle/exemplo"
        )

        evento_salvo = Evento(**dados.model_dump())
        evento_salvo.evento_id = 1
        mock_repositorio.salvar.return_value = evento_salvo

        resultado = servico.criar_evento(dados)

        assert resultado.formulario_link == "https://forms.gle/exemplo"

    def test_aceita_link_de_galeria(self, servico, mock_repositorio):
        inicio = datetime.now() + timedelta(days=30)
        fim = inicio + timedelta(days=2)
        dados = montar_solicitacao(
            inicio, fim, link_galeria="https://drive.google.com/exemplo"
        )

        evento_salvo = Evento(**dados.model_dump())
        evento_salvo.evento_id = 1
        mock_repositorio.salvar.return_value = evento_salvo

        resultado = servico.criar_evento(dados)

        assert resultado.link_galeria == "https://drive.google.com/exemplo"

    def test_campos_opcionais_nao_bloqueiam_a_criacao(self, servico, mock_repositorio):
        """US02 — campo opcional ausente nao pode impedir o cadastro."""
        inicio = datetime.now() + timedelta(days=30)
        fim = inicio + timedelta(days=2)
        dados = montar_solicitacao(inicio, fim)

        evento_salvo = Evento(**dados.model_dump())
        evento_salvo.evento_id = 1
        mock_repositorio.salvar.return_value = evento_salvo

        resultado = servico.criar_evento(dados)

        assert resultado.formulario_link is None
        assert resultado.link_galeria is None

    def test_tipo_acampamento_e_aceito(self, servico, mock_repositorio):
        """O tipo citado pela cliente ao descrever o evento de 3 dias."""
        inicio = datetime.now() + timedelta(days=30)
        fim = inicio + timedelta(days=2)
        dados = montar_solicitacao(inicio, fim)

        evento_salvo = Evento(**dados.model_dump())
        evento_salvo.evento_id = 1
        mock_repositorio.salvar.return_value = evento_salvo

        resultado = servico.criar_evento(dados)

        assert resultado.tipo_evento == TipoEvento.ACAMPAMENTO
