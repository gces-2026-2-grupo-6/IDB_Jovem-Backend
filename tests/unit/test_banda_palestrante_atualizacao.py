"""
Atualizacao de banda/palestrante (US06, RF47 a RF50).

A edicao era o unico caminho do CRUD sem teste: a rota PUT no controlador
(linhas 61 a 65) e o metodo atualizar do repositorio (26 a 28). Como o
cadastro e reaproveitado entre eventos, uma edicao vale para todos eles —
o teste de repositorio roda contra SQLite em memoria para confirmar isso.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.banda_palestrante.controller import atualizar_banda_palestrante
from src.banda_palestrante.model import BandaPalestrante, Participa
from src.banda_palestrante.repository import RepositorioBandaPalestrante
from src.banda_palestrante.schema import SolicitacaoBandaPalestrante
from src.banda_palestrante.service import ServicoBandaPalestrante

DADOS_NOVOS = SolicitacaoBandaPalestrante(
    nome="Banda Renomeada", link_foto="https://exemplo.com/nova.jpg", profissao="Banda"
)


class TestRotaDeAtualizacao:

    def test_atualiza_e_devolve_o_registro(self):
        servico = MagicMock()
        servico.atualizar_banda_palestrante.return_value = "atualizado"
        resultado = atualizar_banda_palestrante(
            participante_id=3, solicitacao=DADOS_NOVOS, servico=servico, _={}
        )
        servico.atualizar_banda_palestrante.assert_called_once_with(3, DADOS_NOVOS)
        assert resultado == "atualizado"

    def test_convidado_inexistente_responde_404(self):
        servico = MagicMock()
        servico.atualizar_banda_palestrante.side_effect = ValueError("não encontrado")
        with pytest.raises(HTTPException) as erro:
            atualizar_banda_palestrante(
                participante_id=99, solicitacao=DADOS_NOVOS, servico=servico, _={}
            )
        assert erro.value.status_code == 404


@pytest.fixture
def sessao():
    engine = create_engine("sqlite://")
    tabelas = [BandaPalestrante.__table__, Participa.__table__]
    BandaPalestrante.metadata.create_all(engine, tables=tabelas)
    sessao = sessionmaker(bind=engine)()
    yield sessao
    sessao.close()
    engine.dispose()


class TestPersistenciaDaAtualizacao:

    def test_edicao_e_gravada_no_banco(self, sessao):
        repositorio = RepositorioBandaPalestrante(sessao)
        original = repositorio.salvar(BandaPalestrante(nome="Banda Antiga", profissao="Banda"))

        ServicoBandaPalestrante(repositorio).atualizar_banda_palestrante(
            original.participante_id, DADOS_NOVOS
        )
        sessao.expire_all()

        gravado = repositorio.buscar_por_id(original.participante_id)
        assert gravado.nome == "Banda Renomeada"
        assert gravado.link_foto == "https://exemplo.com/nova.jpg"

    def test_edicao_vale_para_todos_os_eventos_vinculados(self, sessao):
        """O cadastro e unico: nao existe copia por evento para ficar desatualizada."""
        repositorio = RepositorioBandaPalestrante(sessao)
        banda = repositorio.salvar(BandaPalestrante(nome="Banda Antiga"))
        sessao.add_all([
            Participa(evento_id=1, participante_id=banda.participante_id),
            Participa(evento_id=2, participante_id=banda.participante_id),
        ])
        sessao.commit()

        ServicoBandaPalestrante(repositorio).atualizar_banda_palestrante(
            banda.participante_id, DADOS_NOVOS
        )

        nomes = (
            sessao.query(BandaPalestrante.nome)
            .join(Participa, Participa.participante_id == BandaPalestrante.participante_id)
            .all()
        )
        assert [n for (n,) in nomes] == ["Banda Renomeada", "Banda Renomeada"]

    def test_atualizar_convidado_inexistente_nao_grava(self, sessao):
        repositorio = RepositorioBandaPalestrante(sessao)
        with pytest.raises(ValueError):
            ServicoBandaPalestrante(repositorio).atualizar_banda_palestrante(999, DADOS_NOVOS)
        assert repositorio.buscar_todos() == []
