"""Schemas do modulo pedido (US21)."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.pedido.schema import SolicitacaoStatusPedido, RespostaPedido, StatusPedido


class TestSolicitacaoStatusPedido:
    @pytest.mark.parametrize(
        "status",
        ["pendente", "em_andamento", "concluido", "cancelado"],
    )
    def test_aceita_cada_status_permitido(self, status):
        dados = SolicitacaoStatusPedido(status=status)
        assert dados.status == StatusPedido(status)

    def test_recusa_status_invalido(self):
        with pytest.raises(ValidationError):
            SolicitacaoStatusPedido(status="comprado")

    def test_recusa_status_vazio(self):
        with pytest.raises(ValidationError):
            SolicitacaoStatusPedido(status="")


class TestRespostaPedido:
    def _dados(self, **sobrescritas):
        base = {
            "pedido_id": 1,
            "produto_id": 2,
            "nome_produto": "Camiseta IDB",
            "nome_solicitante": "Ana",
            "contato_solicitante": "ana@exemplo.org",
            "status": "pendente",
            "resposta_id": "resp-1",
            "criado_em": datetime.now(timezone.utc),
        }
        base.update(sobrescritas)
        return base

    def test_monta_a_resposta_completa(self):
        resposta = RespostaPedido(**self._dados())
        assert resposta.pedido_id == 1
        assert resposta.produto_id == 2
        assert resposta.nome_produto == "Camiseta IDB"
        assert resposta.status == StatusPedido.PENDENTE

    def test_resposta_id_e_opcional(self):
        dados = self._dados()
        del dados["resposta_id"]
        resposta = RespostaPedido(**dados)
        assert resposta.resposta_id is None

    def test_recusa_sem_nome_produto(self):
        dados = self._dados()
        del dados["nome_produto"]
        with pytest.raises(ValidationError):
            RespostaPedido(**dados)

    def test_le_a_partir_de_atributos_de_objeto(self):
        class _PedidoFake:
            pedido_id = 1
            produto_id = 2
            nome_produto = "Camiseta IDB"
            nome_solicitante = "Ana"
            contato_solicitante = "ana@exemplo.org"
            status = "pendente"
            resposta_id = None
            criado_em = datetime.now(timezone.utc)

        resposta = RespostaPedido.model_validate(_PedidoFake())
        assert resposta.nome_produto == "Camiseta IDB"
