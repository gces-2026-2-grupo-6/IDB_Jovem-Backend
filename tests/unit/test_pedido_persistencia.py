"""
Persistencia do modelo Pedido (US21): FK com produto, check constraint de
status e o join usado pela listagem. Mesmo molde de test_exclusao_com_vinculo.py
— SQLite com PRAGMA foreign_keys=ON, porque o Postgres aplica isso sempre.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event as sqlalchemy_event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.pedido.model import Pedido
from src.pedido.repository import RepositorioPedido
from src.produto.model import Produto


@pytest.fixture
def sessao():
    engine = create_engine("sqlite://")

    @sqlalchemy_event.listens_for(engine, "connect")
    def _ligar_chaves(conexao, _):
        conexao.execute("PRAGMA foreign_keys=ON")

    Produto.metadata.create_all(engine, tables=[Produto.__table__, Pedido.__table__])
    sessao = sessionmaker(bind=engine)()
    yield sessao
    sessao.close()
    engine.dispose()


def _produto(sessao, produto_id=1, nome="Camiseta IDB"):
    produto = Produto(produto_id=produto_id, nome=nome)
    sessao.add(produto)
    sessao.commit()
    return produto


def test_pedido_nasce_pendente_com_data_e_id(sessao):
    _produto(sessao)
    pedido = Pedido(
        produto_id=1, nome_solicitante="Ana", contato_solicitante="ana@exemplo.org"
    )
    sessao.add(pedido)
    sessao.commit()

    assert pedido.pedido_id is not None
    assert pedido.status == "pendente"
    assert isinstance(pedido.criado_em, datetime)


def test_status_invalido_e_recusado_pelo_banco(sessao):
    _produto(sessao)
    pedido = Pedido(
        produto_id=1,
        nome_solicitante="Ana",
        contato_solicitante="ana@exemplo.org",
        status="comprado",
    )
    sessao.add(pedido)
    with pytest.raises(IntegrityError):
        sessao.commit()


def test_pedido_exige_produto_existente(sessao):
    pedido = Pedido(
        produto_id=999, nome_solicitante="Ana", contato_solicitante="ana@exemplo.org"
    )
    sessao.add(pedido)
    with pytest.raises(IntegrityError):
        sessao.commit()


def test_excluir_produto_nao_apaga_pedidos_no_banco(sessao):
    """
    A FK e simples (sem ON DELETE), igual a trabalha/participa: o banco deixa
    a decisao para a camada de servico (US21 bloqueia a exclusao antes disso).
    """
    produto = _produto(sessao)
    pedido = Pedido(
        produto_id=1, nome_solicitante="Ana", contato_solicitante="ana@exemplo.org"
    )
    sessao.add(pedido)
    sessao.commit()

    sessao.delete(produto)
    with pytest.raises(IntegrityError):
        sessao.commit()


def test_listar_todos_com_produto_traz_nome_do_produto_correto(sessao):
    _produto(sessao, produto_id=1, nome="Camiseta IDB")
    _produto(sessao, produto_id=2, nome="Boné IDB")
    sessao.add_all(
        [
            Pedido(produto_id=1, nome_solicitante="Ana", contato_solicitante="a@x.com"),
            Pedido(produto_id=2, nome_solicitante="Bia", contato_solicitante="b@x.com"),
        ]
    )
    sessao.commit()

    repositorio = RepositorioPedido(sessao)
    linhas = {nome: pedido.nome_solicitante for pedido, nome in repositorio.buscar_todos_com_produto()}

    assert linhas == {"Camiseta IDB": "Ana", "Boné IDB": "Bia"}


def test_lista_vazia_quando_nao_ha_pedidos(sessao):
    _produto(sessao)
    repositorio = RepositorioPedido(sessao)
    assert repositorio.buscar_todos_com_produto() == []


def test_contar_por_produto_bate_com_os_vinculos_reais(sessao):
    _produto(sessao, produto_id=1)
    _produto(sessao, produto_id=2, nome="Boné IDB")
    sessao.add_all(
        [
            Pedido(produto_id=1, nome_solicitante="Ana", contato_solicitante="a@x.com"),
            Pedido(produto_id=1, nome_solicitante="Bia", contato_solicitante="b@x.com"),
            Pedido(produto_id=2, nome_solicitante="Caio", contato_solicitante="c@x.com"),
        ]
    )
    sessao.commit()

    repositorio = RepositorioPedido(sessao)
    assert repositorio.contar_por_produto(1) == 2
    assert repositorio.contar_por_produto(2) == 1
    assert repositorio.contar_por_produto(3) == 0
