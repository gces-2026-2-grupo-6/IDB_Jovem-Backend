"""
Persistencia do modelo Pedido (US21): FK com produto, check constraint de
status e o join usado pela listagem. Mesmo molde de test_exclusao_com_vinculo.py
— SQLite com PRAGMA foreign_keys=ON, porque o Postgres aplica isso sempre.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event as sqlalchemy_event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.formulario.repository import RepositorioFormulario
from src.pedido.model import Pedido
from src.pedido.repository import RepositorioPedido
from src.pedido.schema import SolicitacaoStatusPedido
from src.pedido.service import ServicoPedido
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


# ---------------------------------------------------------------- ressincronizar
#
# Limite registrado na Sprint 4: "a ressincronizacao preserva a situacao do
# pedido, porque o codigo so atualiza o nome e o contato. Mas nenhum teste
# afirma isso explicitamente." Aqui a sincronizacao roda inteira sobre o banco
# (SQLite com chaves ligadas); so as chamadas HTTP ao Google sao simuladas.

LINK_FORMS = "https://docs.google.com/forms/d/ped123/edit"

FORMULARIO_GOOGLE = {
    "items": [
        {"title": "Nome", "questionItem": {"question": {"questionId": "q-nome"}}},
        {"title": "Email", "questionItem": {"question": {"questionId": "q-email"}}},
    ]
}


def _resposta_google(resposta_id, nome, contato):
    return {
        "responseId": resposta_id,
        "answers": {
            "q-nome": {"textAnswers": {"answers": [{"value": nome}]}},
            "q-email": {"textAnswers": {"answers": [{"value": contato}]}},
        },
    }


@pytest.fixture
def sincronizar(sessao):
    """Roda a sincronizacao real do produto 1 com as respostas informadas."""
    produto = Produto(produto_id=1, nome="Camiseta IDB", formulario_pedido_link=LINK_FORMS)
    sessao.add(produto)
    sessao.commit()

    with patch("src.formulario.repository.ServicoAuth"):
        repositorio = RepositorioFormulario()
    repositorio._obter_token_valido = MagicMock(return_value="token")
    repositorio._buscar_formulario = MagicMock(return_value=FORMULARIO_GOOGLE)

    def _executar(*respostas):
        repositorio._buscar_respostas = MagicMock(return_value=list(respostas))
        return repositorio.listar_pedidos(sessao, 1)

    return _executar


def test_primeira_sincronizacao_grava_um_pedido_pendente_por_resposta(sessao, sincronizar):
    lista = sincronizar(
        _resposta_google("r-1", "Ana", "ana@exemplo.org"),
        _resposta_google("r-2", "Bia", "bia@exemplo.org"),
    )

    assert [p.nome_solicitante for p in lista] == ["Ana", "Bia"]
    assert {p.status for p in lista} == {"pendente"}
    assert sessao.query(Pedido).count() == 2


def test_ressincronizar_preserva_a_situacao_dada_pelo_setor(sessao, sincronizar):
    """US21 CA2: a situacao e do setor; o formulario so traz quem pediu."""
    (pedido,) = sincronizar(_resposta_google("r-1", "Ana", "ana@exemplo.org"))
    ServicoPedido(RepositorioPedido(sessao)).atualizar_status(
        pedido.pedido_id, SolicitacaoStatusPedido(status="concluido")
    )

    (ressincronizado,) = sincronizar(
        _resposta_google("r-1", "Ana Souza", "ana@novo.org")
    )

    assert ressincronizado.pedido_id == pedido.pedido_id
    assert ressincronizado.status == "concluido"
    assert ressincronizado.nome_solicitante == "Ana Souza"
    assert ressincronizado.contato_solicitante == "ana@novo.org"
    sessao.expire_all()
    gravado = sessao.get(Pedido, pedido.pedido_id)
    assert gravado.status == "concluido"
    assert sessao.query(Pedido).count() == 1


def test_resposta_nova_nao_mexe_nos_pedidos_ja_tratados(sessao, sincronizar):
    (antigo,) = sincronizar(_resposta_google("r-1", "Ana", "ana@exemplo.org"))
    ServicoPedido(RepositorioPedido(sessao)).atualizar_status(
        antigo.pedido_id, SolicitacaoStatusPedido(status="cancelado")
    )

    lista = sincronizar(
        _resposta_google("r-1", "Ana", "ana@exemplo.org"),
        _resposta_google("r-2", "Bia", "bia@exemplo.org"),
    )

    situacoes = {p.resposta_id: p.status for p in lista}
    assert situacoes == {"r-1": "cancelado", "r-2": "pendente"}
    assert sessao.query(Pedido).count() == 2
