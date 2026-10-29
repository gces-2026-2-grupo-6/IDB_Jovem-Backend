"""
Exclusao de registro que tem vinculos (defeito QA08, Sprint 2).

O defeito original: nenhuma chave estrangeira de `trabalha`, `participa` e
`atividade` declara ON DELETE. No Postgres, excluir um evento referenciado
violava a chave e o erro subia como 500 — e o servico apagava o evento do
Google Calendar ANTES de o banco recusar, deixando o site e a agenda
desencontrados.

A US20 decidiu a Opcao A: o evento sai junto com as inscricoes, a programacao
e os vinculos com convidados; o cadastro das pessoas continua. Os testes
abaixo cobrem o evento. A exclusao de convidado vinculado a evento segue
pendente de decisao (D09) e continua marcada como xfail.
"""

from unittest.mock import MagicMock
from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import Column, Integer, create_engine, event as sqlalchemy_event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base, sessionmaker

from src.atividade.model import Atividade
from src.banda_palestrante.controller import deletar_banda_palestrante
from src.banda_palestrante.model import BandaPalestrante, Participa
from src.banda_palestrante.repository import RepositorioBandaPalestrante
from src.banda_palestrante.service import ServicoBandaPalestrante
from src.evento.model import Evento
from src.evento.repository import RepositorioEvento
from src.evento.service import ServicoEvento
from src.participante.models import Inscricao, Participante
from src.voluntario.models import Trabalha, Voluntario

DEFEITO_CONVIDADO = (
    "D09 pendente: a exclusao de convidado vinculado a evento ainda nao "
    "tem decisao de negocio. Remova o xfail quando ela entrar."
)

# O Evento real usa ARRAY, que o SQLite nao aceita. Para testar a exclusao
# basta a chave: a classe abaixo mapeia a mesma tabela `evento` simplificada.
BaseTeste = declarative_base()


class EventoTeste(BaseTeste):
    __tablename__ = "evento"

    evento_id = Column(Integer, primary_key=True)


@pytest.fixture
def sessao_com_chaves_estrangeiras():
    """SQLite so aplica chave estrangeira com o pragma ligado — como o Postgres faz sempre."""
    engine = create_engine("sqlite://")

    @sqlalchemy_event.listens_for(engine, "connect")
    def _ligar_chaves(conexao, _):
        conexao.execute("PRAGMA foreign_keys=ON")

    with engine.begin() as conexao:
        conexao.exec_driver_sql("CREATE TABLE evento (evento_id INTEGER PRIMARY KEY)")

    tabelas = [
        Participante.__table__,
        Inscricao.__table__,
        Voluntario.__table__,
        Trabalha.__table__,
        BandaPalestrante.__table__,
        Participa.__table__,
        Atividade.__table__,
    ]
    BandaPalestrante.metadata.create_all(engine, tables=tabelas)
    sessao = sessionmaker(bind=engine)()
    yield sessao
    sessao.close()
    engine.dispose()


def _evento_com_vinculos(sessao):
    """Cria um evento com uma linha em cada tabela que aponta para ele."""
    sessao.add(EventoTeste(evento_id=1))
    sessao.add(Participante(participante_id=10, nome="Ana", email="ana@exemplo.com"))
    sessao.add(Voluntario(voluntario_id=20, nome="Bia", email="bia@exemplo.com"))
    sessao.add(BandaPalestrante(participante_id=30, nome="Banda Teste"))
    sessao.commit()

    sessao.add_all([
        Inscricao(participante_id=10, evento_id=1),
        Trabalha(voluntario_id=20, evento_id=1, status="aprovado"),
        Participa(evento_id=1, participante_id=30),
        Atividade(
            atividade_id=40,
            nome="Roda de conversa",
            horario_inicio=datetime(2026, 1, 1, 10, 0),
            horario_termino=datetime(2026, 1, 1, 11, 0),
            evento_id=1,
        ),
    ])
    sessao.commit()
    return sessao.get(EventoTeste, 1)


def test_banco_recusa_excluir_convidado_vinculado(sessao_com_chaves_estrangeiras):
    """Confirma a causa do defeito de convidado: a exclusao viola `participa`."""
    sessao = sessao_com_chaves_estrangeiras
    repositorio = RepositorioBandaPalestrante(sessao)
    banda = repositorio.salvar(BandaPalestrante(nome="Banda Teste"))
    sessao.add(EventoTeste(evento_id=1))
    sessao.add(Participa(evento_id=1, participante_id=banda.participante_id))
    sessao.commit()

    with pytest.raises(IntegrityError):
        repositorio.deletar(banda)


@pytest.mark.xfail(strict=True, reason=DEFEITO_CONVIDADO)
def test_excluir_convidado_vinculado_nao_responde_500(sessao_com_chaves_estrangeiras):
    """Esperado: 409 com mensagem clara, ou exclusao dos vinculos junto."""
    sessao = sessao_com_chaves_estrangeiras
    repositorio = RepositorioBandaPalestrante(sessao)
    banda = repositorio.salvar(BandaPalestrante(nome="Banda Teste"))
    sessao.add(EventoTeste(evento_id=1))
    sessao.add(Participa(evento_id=1, participante_id=banda.participante_id))
    sessao.commit()

    try:
        deletar_banda_palestrante(
            participante_id=banda.participante_id,
            servico=ServicoBandaPalestrante(repositorio),
            _={},
        )
    except HTTPException as erro:
        assert erro.status_code == 409
    except IntegrityError:
        pytest.fail("IntegrityError escapou do controlador e vira 500.")


def test_resumo_conta_inscricoes_atividades_e_convidados(sessao_com_chaves_estrangeiras):
    """US20 (A1): a contagem do modal bate com o que existe no banco."""
    sessao = sessao_com_chaves_estrangeiras
    _evento_com_vinculos(sessao)

    resumo = RepositorioEvento(sessao).contar_vinculos(1)

    assert resumo == {
        "participantes": 1,
        "voluntarios": 1,
        "atividades": 1,
        "convidados": 1,
    }


def test_exclusao_apaga_evento_inscricoes_programacao_e_convidados(
    sessao_com_chaves_estrangeiras,
):
    """US20 (A2): tudo sai junto, mas o cadastro das pessoas continua."""
    sessao = sessao_com_chaves_estrangeiras
    evento = _evento_com_vinculos(sessao)
    repositorio = RepositorioEvento(sessao)

    repositorio.preparar_exclusao(evento)
    repositorio.confirmar_exclusao()

    assert sessao.get(EventoTeste, 1) is None
    assert sessao.query(Inscricao).count() == 0
    assert sessao.query(Trabalha).count() == 0
    assert sessao.query(Participa).count() == 0
    assert sessao.query(Atividade).count() == 0

    # O cadastro em si nao e excluido: a pessoa pode se inscrever em outro evento.
    assert sessao.get(Participante, 10) is not None
    assert sessao.get(Voluntario, 20) is not None
    assert sessao.get(BandaPalestrante, 30) is not None


def test_cancelar_exclusao_desfaz_tudo(sessao_com_chaves_estrangeiras):
    """US20 (A3): rollback devolve evento e vinculos quando alguma etapa falha."""
    sessao = sessao_com_chaves_estrangeiras
    evento = _evento_com_vinculos(sessao)
    repositorio = RepositorioEvento(sessao)

    repositorio.preparar_exclusao(evento)
    repositorio.cancelar_exclusao()

    assert sessao.get(EventoTeste, 1) is not None
    assert sessao.query(Inscricao).count() == 1
    assert sessao.query(Trabalha).count() == 1
    assert sessao.query(Participa).count() == 1
    assert sessao.query(Atividade).count() == 1


def test_agenda_nao_perde_evento_quando_o_banco_recusa_a_exclusao():
    """US20 (A3): falha no banco acontece antes de tocar na agenda do Google."""
    repositorio = MagicMock()
    repositorio.buscar_por_id.return_value = Evento(
        evento_id=1, nome="Retiro", calendario_evento_id="google-123"
    )
    repositorio.preparar_exclusao.side_effect = IntegrityError("DELETE", {}, Exception("fk"))
    calendario = MagicMock()
    servico = ServicoEvento(repositorio, calendario, MagicMock())

    with pytest.raises(IntegrityError):
        servico.deletar_evento(1)

    calendario.deletar_evento.assert_not_called()
    repositorio.confirmar_exclusao.assert_not_called()
    repositorio.cancelar_exclusao.assert_called_once()


def test_agenda_falha_desfaz_exclusao_no_banco():
    """US20 (A3): se o Google recusar, o banco volta ao estado anterior."""
    repositorio = MagicMock()
    repositorio.buscar_por_id.return_value = Evento(
        evento_id=1, nome="Retiro", calendario_evento_id="google-123"
    )
    calendario = MagicMock()
    calendario.deletar_evento.side_effect = RuntimeError("Falha ao deletar")
    servico = ServicoEvento(repositorio, calendario, MagicMock())

    with pytest.raises(RuntimeError):
        servico.deletar_evento(1)

    repositorio.preparar_exclusao.assert_called_once()
    repositorio.confirmar_exclusao.assert_not_called()
    repositorio.cancelar_exclusao.assert_called_once()
