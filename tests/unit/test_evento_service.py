import pytest
from unittest.mock import MagicMock
from src.evento.service import ServicoEvento
from src.evento.model import Evento
from src.evento.schema import SolicitacaoEvento, TipoEvento
from datetime import datetime, timedelta

@pytest.fixture
def mock_repositorio():
    return MagicMock()

@pytest.fixture
def mock_calendario():
    return MagicMock()

@pytest.fixture
def mock_mapa():
    return MagicMock()

@pytest.fixture
def servico(mock_repositorio, mock_calendario, mock_mapa):
    return ServicoEvento(
        repositorio=mock_repositorio,
        google_calendario=mock_calendario,
        mapa_servico=mock_mapa
    )

def test_criar_evento(servico, mock_repositorio, mock_calendario, mock_mapa):
    dados = SolicitacaoEvento(
        nome="Teste", 
        data_inicio=datetime.now() + timedelta(days=1), 
        data_fim=datetime.now() + timedelta(days=1, hours=1),
        local_latitude=-15.7942,
        local_longitude=-47.8822,
        descricao="Desc",
        tipo_evento=TipoEvento.CONFERENCIA
    )
    
    evento_mock = Evento(**dados.model_dump())
    evento_mock.evento_id = 1
    
    mock_repositorio.salvar.return_value = evento_mock
    mock_mapa.buscar_endereco_por_coordenadas.return_value = "Endereço Teste"
    mock_calendario.criar_evento.return_value = "cal-id-123"
    
    resultado = servico.criar_evento(dados)
    
    assert mock_repositorio.salvar.call_count == 3
    mock_calendario.criar_evento.assert_called_once()
    assert resultado.calendario_evento_id == "cal-id-123"

def test_criar_evento_erro_calendario(servico, mock_repositorio, mock_calendario, mock_mapa):
    dados = SolicitacaoEvento(
        nome="Teste", 
        data_inicio=datetime.now() + timedelta(days=1), 
        data_fim=datetime.now() + timedelta(days=1, hours=1),
        local_latitude=0.0,
        local_longitude=0.0,
        descricao="Desc",
        tipo_evento=TipoEvento.CONFERENCIA
    )
    evento_mock = Evento(**dados.model_dump())
    mock_repositorio.salvar.return_value = evento_mock
    mock_calendario.criar_evento.side_effect = Exception("Erro API Google")
    
    with pytest.raises(Exception, match="Erro API Google"):
        servico.criar_evento(dados)

def test_buscar_evento_nao_encontrado(servico, mock_repositorio):
    mock_repositorio.buscar_por_id.return_value = None
    with pytest.raises(ValueError, match="Evento não encontrado."):
        servico.buscar_evento(1)

def test_atualizar_evento(servico, mock_repositorio, mock_calendario, mock_mapa):
    evento = Evento(evento_id=1, nome="Antigo", calendario_evento_id="cal-id")
    mock_repositorio.buscar_por_id.return_value = evento
    
    mudancas = SolicitacaoEvento(
        nome="Novo", 
        data_inicio=datetime.now() + timedelta(days=1), 
        data_fim=datetime.now() + timedelta(days=1, hours=1),
        local_latitude=0.0,
        local_longitude=0.0,
        descricao="Desc",
        tipo_evento=TipoEvento.CONFERENCIA
    )
    
    servico.atualizar_evento(1, mudancas)
    
    mock_repositorio.salvar.assert_called_once()
    mock_calendario.atualizar_evento.assert_called_once()

def test_deletar_evento(servico, mock_repositorio, mock_calendario):
    evento = Evento(evento_id=1, calendario_evento_id="cal-id")
    mock_repositorio.buscar_por_id.return_value = evento
    
    servico.deletar_evento(1)
    
    mock_calendario.deletar_evento.assert_called_once_with("cal-id")
    mock_repositorio.deletar.assert_called_once_with(evento)

def test_listar_eventos(servico, mock_repositorio):
    servico.listar_evento()
    mock_repositorio.buscar_todos.assert_called_once()

def test_pesquisar_eventos_curto(servico):
    assert servico.pesquisar_eventos("a") == []

def test_pesquisar_eventos_valido(servico, mock_repositorio):
    servico.pesquisar_eventos("teste")
    mock_repositorio.pesquisar_por_nome.assert_called_once_with("teste")
