from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.drive.schema import RespostaDrive
from src.evento.controller import get_servico, router as evento_router
from src.evento.model import Evento, FotoExcluidaEvento
from src.evento.repository import RepositorioEvento
from src.evento.schema import SolicitacaoFotosExcluidas
from src.evento.service import ServicoEvento
from src.security import obter_usuario_atual


@pytest.fixture
def sessao_sqlite():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _ligar_fk(conexao, _):
        conexao.execute("PRAGMA foreign_keys=ON")

    with engine.begin() as conexao:
        conexao.exec_driver_sql("CREATE TABLE evento (evento_id INTEGER PRIMARY KEY)")
        conexao.exec_driver_sql("INSERT INTO evento VALUES (1), (2)")

    FotoExcluidaEvento.__table__.create(engine)
    sessao = sessionmaker(bind=engine)()
    yield sessao
    sessao.close()
    engine.dispose()


def _evento(evento_id: int = 1, nome: str = "Retiro", link_galeria: str = "pasta-1"):
    agora = datetime.now()
    return Evento(
        evento_id=evento_id,
        nome=nome,
        link_galeria=link_galeria,
        nome_local="Brasília",
        data_inicio=agora,
        data_fim=agora + timedelta(days=1),
        local_latitude=-15.79,
        local_longitude=-47.88,
    )


def _client(servico: ServicoEvento, papeis: list[str]) -> TestClient:
    app = FastAPI()
    app.include_router(evento_router)
    app.dependency_overrides[get_servico] = lambda: servico
    app.dependency_overrides[obter_usuario_atual] = lambda: {
        "sub": "u-1",
        "realm_access": {"roles": papeis},
    }
    return TestClient(app)


class TestSchemaFotosExcluidas:

    def test_lista_valida_remove_espacos_e_duplicatas(self):
        dados = SolicitacaoFotosExcluidas(fotos=["  g1 ", "g2", "g1", ""])
        assert dados.fotos == ["g1", "g2"]

    @pytest.mark.parametrize("fotos", [[], ["", "   "]])
    def test_lista_vazia_ou_em_branco_e_recusada(self, fotos):
        with pytest.raises(ValidationError):
            SolicitacaoFotosExcluidas(fotos=fotos)


class TestRepositorioFotosExcluidas:

    def test_registra_e_busca_fotos_por_evento(self, sessao_sqlite):
        repo = RepositorioEvento(sessao_sqlite)

        repo.registrar_fotos_excluidas(1, ["g1", "g2"])

        assert repo.buscar_fotos_excluidas(1) == {"g1", "g2"}
        assert repo.buscar_fotos_excluidas(2) == set()

    def test_registro_e_idempotente(self, sessao_sqlite):
        repo = RepositorioEvento(sessao_sqlite)

        repo.registrar_fotos_excluidas(1, ["g1"])
        repo.registrar_fotos_excluidas(1, ["g1", "g2"])
        repo.registrar_fotos_excluidas(1, ["g1"])

        assert repo.buscar_fotos_excluidas(1) == {"g1", "g2"}

    def test_excluir_evento_apaga_fotos_excluidas_em_cascata(self, sessao_sqlite):
        repo = RepositorioEvento(sessao_sqlite)
        repo.registrar_fotos_excluidas(1, ["g1", "g2"])

        sessao_sqlite.execute(text("DELETE FROM evento WHERE evento_id = 1"))
        sessao_sqlite.commit()

        assert repo.buscar_fotos_excluidas(1) == set()


class TestServicoFotosExcluidas:

    def test_exclui_fotos_quando_evento_existe(self):
        repo = MagicMock()
        repo.buscar_por_id.return_value = _evento(1)
        servico = ServicoEvento(repo, MagicMock(), MagicMock())

        servico.excluir_fotos_galeria(1, SolicitacaoFotosExcluidas(fotos=["g1"]))

        repo.registrar_fotos_excluidas.assert_called_once_with(1, ["g1"])

    def test_recusa_quando_evento_nao_existe(self):
        repo = MagicMock()
        repo.buscar_por_id.return_value = None
        servico = ServicoEvento(repo, MagicMock(), MagicMock())

        with pytest.raises(ValueError, match="Evento não encontrado"):
            servico.excluir_fotos_galeria(99, SolicitacaoFotosExcluidas(fotos=["g1"]))

        repo.registrar_fotos_excluidas.assert_not_called()

    def test_lista_fotos_excluidas_do_evento(self):
        repo = MagicMock()
        repo.buscar_fotos_excluidas.return_value = {"g1", "g3"}
        servico = ServicoEvento(repo, MagicMock(), MagicMock())

        assert servico.listar_fotos_excluidas(1) == {"g1", "g3"}
        repo.buscar_fotos_excluidas.assert_called_once_with(1)


class TestControllerFotosExcluidas:

    def test_superadmin_exclui_fotos_e_recebe_204(self, sessao_sqlite):
        repo = RepositorioEvento(sessao_sqlite)
        repo.buscar_por_id = MagicMock(return_value=_evento(1))
        servico = ServicoEvento(repo, MagicMock(), MagicMock())

        resposta = _client(servico, ["superadmin"]).post(
            "/evento/1/galeria/excluidas",
            json={"fotos": ["g1"]},
        )

        assert resposta.status_code == 204
        assert repo.buscar_fotos_excluidas(1) == {"g1"}

    def test_admin_de_setor_recebe_403(self):
        servico = MagicMock()
        resposta = _client(servico, ["admin", "admin-eventos"]).post(
            "/evento/1/galeria/excluidas",
            json={"fotos": ["g1"]},
        )

        assert resposta.status_code == 403
        servico.excluir_fotos_galeria.assert_not_called()

    def test_evento_inexistente_responde_404(self):
        repo = MagicMock()
        repo.buscar_por_id.return_value = None
        servico = ServicoEvento(repo, MagicMock(), MagicMock())

        resposta = _client(servico, ["superadmin"]).post(
            "/evento/999/galeria/excluidas",
            json={"fotos": ["g1"]},
        )

        assert resposta.status_code == 404

    def test_lista_vazia_responde_422(self):
        servico = MagicMock()
        resposta = _client(servico, ["superadmin"]).post(
            "/evento/1/galeria/excluidas",
            json={"fotos": []},
        )

        assert resposta.status_code == 422

    @patch("src.evento.controller.ServicoDrive")
    def test_foto_excluida_some_da_galeria_e_capa_passa_para_a_seguinte(
        self, mock_drive_cls, sessao_sqlite
    ):
        repo = RepositorioEvento(sessao_sqlite)
        repo.buscar_por_id = MagicMock(return_value=_evento(1, "Retiro", "pasta-1"))
        servico = ServicoEvento(repo, MagicMock(), MagicMock())

        drive = MagicMock()
        drive.listar_fotos.return_value = [
            RespostaDrive(id="g1", nome="capa.jpg", url_visualizacao="http://proxy/g1"),
            RespostaDrive(id="g2", nome="foto2.jpg", url_visualizacao="http://proxy/g2"),
        ]
        mock_drive_cls.return_value = drive

        client = _client(servico, ["superadmin"])
        exclusao = client.post("/evento/1/galeria/excluidas", json={"fotos": ["g1"]})
        assert exclusao.status_code == 204

        galeria = client.get("/evento/1/galeria")
        assert galeria.status_code == 200
        fotos = galeria.json()
        assert [f["id"] for f in fotos] == ["g2"]
        drive.listar_fotos.assert_called_once_with("pasta-1")

    @patch("src.evento.controller.ServicoDrive")
    def test_exclusao_filtra_galeria_geral_sem_afetar_outros_eventos(
        self, mock_drive_cls, sessao_sqlite
    ):
        repo = RepositorioEvento(sessao_sqlite)
        ev1 = _evento(1, "Retiro", "pasta-retiro")
        ev2 = _evento(2, "Congresso", "pasta-congresso")
        repo.buscar_por_id = MagicMock(
            side_effect=lambda eid: ev1 if eid == 1 else ev2
        )
        repo.buscar_todos = MagicMock(return_value=[ev1, ev2])
        servico = ServicoEvento(repo, MagicMock(), MagicMock())

        drive = MagicMock()
        drive.listar_fotos.side_effect = lambda pasta: (
            [
                RespostaDrive(id="g1", nome="1.jpg", url_visualizacao="http://p/g1"),
                RespostaDrive(id="g2", nome="2.jpg", url_visualizacao="http://p/g2"),
            ]
            if pasta == "pasta-retiro"
            else [
                RespostaDrive(id="g3", nome="3.jpg", url_visualizacao="http://p/g3"),
            ]
        )
        mock_drive_cls.return_value = drive

        client = _client(servico, ["superadmin"])
        client.post("/evento/1/galeria/excluidas", json={"fotos": ["g1"]})

        todas = client.get("/evento/galerias/todas")
        assert todas.status_code == 200
        itens = todas.json()
        assert [(item["id"], item["event"]) for item in itens] == [
            ("g2", "Retiro"),
            ("g3", "Congresso"),
        ]

