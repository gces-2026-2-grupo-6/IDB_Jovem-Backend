"""
Vinculo entre evento e banda/palestrante por identificador (US06, RF47 a RF50).

A US06 tornou bandas e palestrantes reaproveitaveis entre eventos: o cadastro
e unico e cada evento apenas aponta para ele pela tabela "participa". Ate a
Sprint 2, os metodos que criam, consultam e desfazem esse vinculo nao tinham
teste — service linhas 98 a 119 e repository 46 a 81 sem cobertura.

O repositorio e testado contra SQLite em memoria, criando so as tabelas do
vinculo: a tabela de evento usa ARRAY, que o SQLite nao suporta, e a regra
coberta aqui nao depende dela.
"""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.banda_palestrante.model import BandaPalestrante, Participa
from src.evento.model import Evento
from src.evento.repository import RepositorioEvento
from src.evento.service import ServicoEvento

EVENTO_A = 1
EVENTO_B = 2


# ---------------------------------------------------------------------------
# Servico: regras de negocio com repositorio simulado
# ---------------------------------------------------------------------------

@pytest.fixture
def repositorio_simulado():
    repo = MagicMock()
    repo.buscar_por_id.return_value = Evento(evento_id=EVENTO_A, nome="Retiro")
    repo.buscar_participante_por_id.return_value = BandaPalestrante(
        participante_id=7, nome="Banda Teste"
    )
    repo.buscar_vinculo.return_value = None
    return repo


@pytest.fixture
def servico(repositorio_simulado):
    return ServicoEvento(repositorio_simulado, MagicMock(), MagicMock())


class TestAdicionarParticipante:

    def test_vincula_e_devolve_o_participante(self, servico, repositorio_simulado):
        participante = servico.adicionar_participante(EVENTO_A, 7)
        repositorio_simulado.vincular_participante.assert_called_once_with(EVENTO_A, 7)
        assert participante.participante_id == 7

    def test_evento_inexistente_nao_vincula(self, servico, repositorio_simulado):
        repositorio_simulado.buscar_por_id.return_value = None
        with pytest.raises(ValueError, match="Evento"):
            servico.adicionar_participante(99, 7)
        repositorio_simulado.vincular_participante.assert_not_called()

    def test_participante_inexistente_nao_vincula(self, servico, repositorio_simulado):
        repositorio_simulado.buscar_participante_por_id.return_value = None
        with pytest.raises(ValueError, match="Banda ou palestrante"):
            servico.adicionar_participante(EVENTO_A, 99)
        repositorio_simulado.vincular_participante.assert_not_called()

    def test_vinculo_repetido_e_recusado(self, servico, repositorio_simulado):
        repositorio_simulado.buscar_vinculo.return_value = Participa(
            evento_id=EVENTO_A, participante_id=7
        )
        with pytest.raises(ValueError, match="já vinculado"):
            servico.adicionar_participante(EVENTO_A, 7)
        repositorio_simulado.vincular_participante.assert_not_called()


class TestListarParticipantes:

    def test_lista_os_participantes_do_evento(self, servico, repositorio_simulado):
        repositorio_simulado.buscar_participantes.return_value = ["p1", "p2"]
        assert servico.listar_participantes(EVENTO_A) == ["p1", "p2"]
        repositorio_simulado.buscar_participantes.assert_called_once_with(EVENTO_A)

    def test_evento_inexistente_e_erro(self, servico, repositorio_simulado):
        repositorio_simulado.buscar_por_id.return_value = None
        with pytest.raises(ValueError):
            servico.listar_participantes(99)
        repositorio_simulado.buscar_participantes.assert_not_called()


class TestRemoverParticipante:

    def test_desfaz_o_vinculo_existente(self, servico, repositorio_simulado):
        vinculo = Participa(evento_id=EVENTO_A, participante_id=7)
        repositorio_simulado.buscar_vinculo.return_value = vinculo
        servico.remover_participante(EVENTO_A, 7)
        repositorio_simulado.desvincular_participante.assert_called_once_with(vinculo)

    def test_vinculo_inexistente_e_erro(self, servico, repositorio_simulado):
        with pytest.raises(ValueError, match="Vínculo"):
            servico.remover_participante(EVENTO_A, 7)
        repositorio_simulado.desvincular_participante.assert_not_called()


# ---------------------------------------------------------------------------
# Repositorio: persistencia real do vinculo
# ---------------------------------------------------------------------------

@pytest.fixture
def sessao():
    engine = create_engine("sqlite://")
    tabelas = [BandaPalestrante.__table__, Participa.__table__]
    BandaPalestrante.metadata.create_all(engine, tables=tabelas)
    sessao = sessionmaker(bind=engine)()
    yield sessao
    sessao.close()
    engine.dispose()


@pytest.fixture
def repositorio(sessao):
    return RepositorioEvento(sessao)


@pytest.fixture
def banda_e_palestrante(sessao):
    banda = BandaPalestrante(nome="Banda Teste", profissao="Banda")
    palestrante = BandaPalestrante(nome="Pr. Fulano", profissao="Palestrante")
    sessao.add_all([banda, palestrante])
    sessao.commit()
    return banda, palestrante


class TestRepositorioDeVinculo:

    def test_vinculo_criado_pode_ser_consultado(self, repositorio, banda_e_palestrante):
        banda, _ = banda_e_palestrante
        repositorio.vincular_participante(EVENTO_A, banda.participante_id)
        vinculo = repositorio.buscar_vinculo(EVENTO_A, banda.participante_id)
        assert vinculo is not None
        assert (vinculo.evento_id, vinculo.participante_id) == (EVENTO_A, banda.participante_id)

    def test_mesmo_convidado_em_dois_eventos(self, repositorio, banda_e_palestrante):
        """O cadastro e reaproveitado: um convidado, varios eventos."""
        banda, _ = banda_e_palestrante
        repositorio.vincular_participante(EVENTO_A, banda.participante_id)
        repositorio.vincular_participante(EVENTO_B, banda.participante_id)
        assert [p.nome for p in repositorio.buscar_participantes(EVENTO_A)] == ["Banda Teste"]
        assert [p.nome for p in repositorio.buscar_participantes(EVENTO_B)] == ["Banda Teste"]

    def test_participantes_de_eventos_distintos_nao_se_misturam(
        self, repositorio, banda_e_palestrante
    ):
        banda, palestrante = banda_e_palestrante
        repositorio.vincular_participante(EVENTO_A, banda.participante_id)
        repositorio.vincular_participante(EVENTO_B, palestrante.participante_id)
        assert [p.nome for p in repositorio.buscar_participantes(EVENTO_A)] == ["Banda Teste"]
        assert [p.nome for p in repositorio.buscar_participantes(EVENTO_B)] == ["Pr. Fulano"]

    def test_evento_sem_vinculo_devolve_lista_vazia(self, repositorio, banda_e_palestrante):
        assert repositorio.buscar_participantes(EVENTO_A) == []

    def test_vinculo_duplicado_e_barrado_pelo_banco(
        self, repositorio, sessao, banda_e_palestrante
    ):
        """A chave primaria composta impede duplicata mesmo se o servico falhar."""
        banda, _ = banda_e_palestrante
        repositorio.vincular_participante(EVENTO_A, banda.participante_id)
        with pytest.raises(IntegrityError):
            repositorio.vincular_participante(EVENTO_A, banda.participante_id)
        sessao.rollback()

    def test_desvincular_remove_so_o_vinculo(self, repositorio, sessao, banda_e_palestrante):
        """O convidado continua cadastrado para outros eventos."""
        banda, _ = banda_e_palestrante
        repositorio.vincular_participante(EVENTO_A, banda.participante_id)
        vinculo = repositorio.buscar_vinculo(EVENTO_A, banda.participante_id)
        repositorio.desvincular_participante(vinculo)
        assert repositorio.buscar_vinculo(EVENTO_A, banda.participante_id) is None
        assert repositorio.buscar_participante_por_id(banda.participante_id) is not None

    def test_buscar_participante_inexistente(self, repositorio, banda_e_palestrante):
        assert repositorio.buscar_participante_por_id(999) is None
