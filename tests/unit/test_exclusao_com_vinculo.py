"""
Exclusao de registro que tem vinculos (defeito aberto, encontrado na Sprint 2).

Nenhuma chave estrangeira do banco declara ON DELETE (migration
2099c20fc4fc_initial). No Postgres, excluir um registro referenciado viola a
chave e o erro sobe como 500, sem que nada seja apagado. Reproduzido com as
migrations do projeto:

    DELETE /banda-palestrante/{id}  convidado vinculado a um evento   -> 500
    DELETE /evento/{id}             evento com convidado vinculado    -> 500
    DELETE /evento/{id}             evento com atividade na programacao -> 500

No caso do evento ha um agravante: o servico apaga o evento do Google
Calendar ANTES de apagar no banco. Quando o banco recusa, o evento continua
no site mas ja sumiu da agenda.

A correcao depende de decisao de negocio — apagar os vinculos junto
(CASCADE) ou recusar a exclusao com 409 — e cabe a quem implementa. Os testes
abaixo usam xfail(strict=True): hoje falham como esperado; quando a correcao
entrar, passam a "passar inesperadamente" e o pytest acusa, obrigando a
remover o xfail e manter o teste como regressao.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.banda_palestrante.controller import deletar_banda_palestrante
from src.banda_palestrante.model import BandaPalestrante, Participa
from src.banda_palestrante.repository import RepositorioBandaPalestrante
from src.banda_palestrante.service import ServicoBandaPalestrante
from src.evento.model import Evento
from src.evento.service import ServicoEvento

DEFEITO = (
    "Defeito aberto na Sprint 2: chaves estrangeiras sem ON DELETE. "
    "Remova o xfail quando a correcao entrar."
)


@pytest.fixture
def sessao_com_chaves_estrangeiras():
    """SQLite so aplica chave estrangeira com o pragma ligado — como o Postgres faz sempre."""
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _ligar_chaves(conexao, _):
        conexao.execute("PRAGMA foreign_keys=ON")

    # A tabela evento real usa ARRAY, que o SQLite nao suporta; basta a chave.
    with engine.begin() as conexao:
        conexao.exec_driver_sql("CREATE TABLE evento (evento_id INTEGER PRIMARY KEY)")
        conexao.exec_driver_sql("INSERT INTO evento VALUES (1)")
    tabelas = [BandaPalestrante.__table__, Participa.__table__]
    BandaPalestrante.metadata.create_all(engine, tables=tabelas)
    sessao = sessionmaker(bind=engine)()
    yield sessao
    sessao.close()
    engine.dispose()


def test_banco_recusa_excluir_convidado_vinculado(sessao_com_chaves_estrangeiras):
    """Confirma a causa: a exclusao viola a chave estrangeira de participa."""
    sessao = sessao_com_chaves_estrangeiras
    repositorio = RepositorioBandaPalestrante(sessao)
    banda = repositorio.salvar(BandaPalestrante(nome="Banda Teste"))
    sessao.add(Participa(evento_id=1, participante_id=banda.participante_id))
    sessao.commit()

    with pytest.raises(IntegrityError):
        repositorio.deletar(banda)


@pytest.mark.xfail(strict=True, reason=DEFEITO)
def test_excluir_convidado_vinculado_nao_responde_500(sessao_com_chaves_estrangeiras):
    """Esperado: 409 com mensagem clara, ou exclusao dos vinculos junto."""
    sessao = sessao_com_chaves_estrangeiras
    repositorio = RepositorioBandaPalestrante(sessao)
    banda = repositorio.salvar(BandaPalestrante(nome="Banda Teste"))
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


@pytest.mark.xfail(strict=True, reason=DEFEITO)
def test_agenda_nao_perde_evento_quando_o_banco_recusa_a_exclusao():
    repositorio = MagicMock()
    repositorio.buscar_por_id.return_value = Evento(
        evento_id=1, nome="Retiro", calendario_evento_id="google-123"
    )
    repositorio.deletar.side_effect = IntegrityError("DELETE", {}, Exception("fk"))
    calendario = MagicMock()
    servico = ServicoEvento(repositorio, calendario, MagicMock())

    with pytest.raises(Exception):
        servico.deletar_evento(1)

    calendario.deletar_evento.assert_not_called()
