"""Fluxo de sincronizacao de pedidos no repositorio de formularios (US21)."""
from datetime import datetime, timezone

import pytest
from unittest.mock import MagicMock, patch

from src.formulario.repository import RepositorioFormulario
from src.pedido.schema import RespostaPedido
from src.pedido.model import Pedido


LINK_FORMS = "https://docs.google.com/forms/d/ped123/edit"


def _repositorio_preparado(produto):
    repo = RepositorioFormulario()
    repo._obter_token_valido = MagicMock(return_value="token")
    repo._buscar_produto = MagicMock(return_value=produto)
    repo._buscar_formulario = MagicMock(return_value={"items": []})
    repo._buscar_respostas = MagicMock(return_value=[])
    return repo


def _produto(produto_id=1, nome="Camiseta IDB", link_pedido=LINK_FORMS):
    produto = MagicMock()
    produto.produto_id = produto_id
    produto.nome = nome
    produto.formulario_pedido_link = link_pedido
    return produto


@patch("src.formulario.repository.ServicoAuth")
class TestBuscarProduto:
    def test_buscar_produto_sucesso(self, _auth):
        repo = RepositorioFormulario()
        mock_db = MagicMock()
        mock_produto = MagicMock()
        mock_db.query().filter().first.return_value = mock_produto

        resultado = repo._buscar_produto(mock_db, 1)
        assert resultado == mock_produto

    def test_buscar_produto_nao_encontrado(self, _auth):
        repo = RepositorioFormulario()
        mock_db = MagicMock()
        mock_db.query().filter().first.return_value = None

        with pytest.raises(ValueError, match="Produto nao encontrado"):
            repo._buscar_produto(mock_db, 1)


@patch("src.formulario.repository.ServicoAuth")
class TestListarPedidos:
    def test_sem_formulario_de_pedido_e_recusado(self, _auth):
        repo = _repositorio_preparado(_produto(link_pedido=None))

        with pytest.raises(ValueError, match="Produto sem formulario de pedidos"):
            repo.listar_pedidos(MagicMock(), 1)

    def test_sem_respostas_devolve_lista_vazia(self, _auth):
        repo = _repositorio_preparado(_produto())
        mock_db = MagicMock()

        assert repo.listar_pedidos(mock_db, 1) == []
        mock_db.commit.assert_called_once()

    def test_usa_o_link_de_pedido_do_produto(self, _auth):
        repo = _repositorio_preparado(_produto())
        repo._definir_formulario_id = MagicMock(return_value="ped123")

        repo.listar_pedidos(MagicMock(), 1)

        repo._definir_formulario_id.assert_called_once_with(LINK_FORMS)

    def test_descarta_respostas_incompletas(self, _auth):
        repo = _repositorio_preparado(_produto())
        repo._buscar_respostas = MagicMock(return_value=[{"r": 1}, {"r": 2}])
        repo._montar_pedido = MagicMock(side_effect=[MagicMock(), None])
        mock_db = MagicMock()

        assert len(repo.listar_pedidos(mock_db, 1)) == 1
        mock_db.commit.assert_called_once()

    def test_produto_nao_encontrado_propaga_o_erro(self, _auth):
        repo = RepositorioFormulario()
        repo._buscar_produto = MagicMock(side_effect=ValueError("Produto nao encontrado"))

        with pytest.raises(ValueError, match="Produto nao encontrado"):
            repo.listar_pedidos(MagicMock(), 999)


@patch("src.formulario.repository.ServicoAuth")
class TestGarantirPedido:
    def test_cria_quando_nao_existe(self, _auth):
        repo = RepositorioFormulario()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        pedido = repo._garantir_pedido(mock_db, 1, "Ana", "ana@exemplo.org", "resp-1")

        assert isinstance(pedido, Pedido)
        assert (pedido.produto_id, pedido.nome_solicitante) == (1, "Ana")
        assert pedido.contato_solicitante == "ana@exemplo.org"
        assert pedido.resposta_id == "resp-1"
        mock_db.add.assert_called_once_with(pedido)
        mock_db.flush.assert_called_once()

    def test_atualiza_quando_a_resposta_ja_existe(self, _auth):
        repo = RepositorioFormulario()
        existente = Pedido(
            pedido_id=7,
            produto_id=1,
            nome_solicitante="Ana",
            contato_solicitante="ana@antigo.org",
            resposta_id="resp-1",
        )
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existente

        pedido = repo._garantir_pedido(mock_db, 1, "Ana Souza", "ana@novo.org", "resp-1")

        assert pedido is existente
        assert pedido.nome_solicitante == "Ana Souza"
        assert pedido.contato_solicitante == "ana@novo.org"
        mock_db.flush.assert_not_called()


@patch("src.formulario.repository.ServicoAuth")
class TestMontarPedido:
    def _contexto(self, mock_db, produto_id=1, nome_produto="Camiseta IDB"):
        produto = MagicMock()
        produto.produto_id = produto_id
        produto.nome = nome_produto
        return {
            "db": mock_db,
            "produto": produto,
            "formulario_id": "ped123",
            "id_nome": "q1",
            "id_email": "q2",
        }

    def _resposta(self, nome="Ana", contato="ana@exemplo.org", resposta_id="resp-1"):
        return {
            "responseId": resposta_id,
            "answers": {
                "q1": {"textAnswers": {"answers": [{"value": nome}]}},
                "q2": {"textAnswers": {"answers": [{"value": contato}]}},
            },
        }

    def test_monta_a_resposta_completa(self, _auth):
        repo = RepositorioFormulario()
        repo._garantir_pedido = MagicMock(
            return_value=Pedido(
                pedido_id=9,
                produto_id=1,
                nome_solicitante="Ana",
                contato_solicitante="ana@exemplo.org",
                resposta_id="resp-1",
                status="pendente",
                criado_em=datetime.now(timezone.utc),
            )
        )
        mock_db = MagicMock()

        resultado = repo._montar_pedido(self._contexto(mock_db), self._resposta())

        assert isinstance(resultado, RespostaPedido)
        assert resultado.pedido_id == 9
        assert resultado.produto_id == 1
        assert resultado.nome_produto == "Camiseta IDB"
        assert resultado.nome_solicitante == "Ana"
        assert resultado.contato_solicitante == "ana@exemplo.org"
        assert resultado.resposta_id == "resp-1"
        repo._garantir_pedido.assert_called_once_with(
            mock_db, 1, "Ana", "ana@exemplo.org", "resp-1"
        )

    @pytest.mark.parametrize(
        "resposta",
        [
            pytest.param({"responseId": "r", "answers": {}}, id="sem_nome_e_contato"),
            pytest.param({"answers": {}}, id="sem_response_id"),
        ],
    )
    def test_descarta_resposta_incompleta(self, _auth, resposta):
        repo = RepositorioFormulario()
        repo._garantir_pedido = MagicMock()

        assert repo._montar_pedido(self._contexto(MagicMock()), resposta) is None
        repo._garantir_pedido.assert_not_called()
