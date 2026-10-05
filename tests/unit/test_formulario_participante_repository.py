"""Fluxo de inscricao de participante no repositorio de formularios (US09)."""
import pytest
from unittest.mock import MagicMock, patch

from src.formulario.repository import RepositorioFormulario
from src.formulario.schema import RespostaInscricaoParticipante
from src.participante.models import Inscricao, Participante


LINK_FORMS = "https://docs.google.com/forms/d/part123/edit"


def _repositorio_preparado(evento):
    repo = RepositorioFormulario()
    repo._obter_token_valido = MagicMock(return_value="token")
    repo._buscar_evento = MagicMock(return_value=evento)
    repo._buscar_formulario = MagicMock(return_value={"items": []})
    repo._buscar_respostas = MagicMock(return_value=[])
    return repo


def _evento(evento_id=1, link_participante=LINK_FORMS, link_voluntario=None):
    evento = MagicMock()
    evento.evento_id = evento_id
    evento.formulario_participante_link = link_participante
    evento.formulario_link = link_voluntario
    return evento


@patch("src.formulario.repository.ServicoAuth")
class TestListarParticipantes:
    def test_sem_formulario_de_participante_e_recusado(self, _auth):
        repo = _repositorio_preparado(_evento(link_participante=None))

        with pytest.raises(ValueError, match="Evento sem formulario de participantes"):
            repo.listar_participantes(MagicMock(), 1)

    def test_formulario_de_voluntario_nao_serve_para_participante(self, _auth):
        """Os dois fluxos tem links proprios: um nao supre a falta do outro."""
        evento = _evento(link_participante=None, link_voluntario=LINK_FORMS)
        repo = _repositorio_preparado(evento)

        with pytest.raises(ValueError, match="Evento sem formulario de participantes"):
            repo.listar_participantes(MagicMock(), 1)

    def test_sem_respostas_devolve_lista_vazia(self, _auth):
        repo = _repositorio_preparado(_evento())
        mock_db = MagicMock()

        assert repo.listar_participantes(mock_db, 1) == []
        mock_db.commit.assert_called_once()

    def test_usa_o_link_de_participante_do_evento(self, _auth):
        repo = _repositorio_preparado(_evento())
        repo._definir_formulario_id = MagicMock(return_value="part123")

        repo.listar_participantes(MagicMock(), 1)

        repo._definir_formulario_id.assert_called_once_with(LINK_FORMS)

    def test_descarta_respostas_incompletas(self, _auth):
        repo = _repositorio_preparado(_evento())
        repo._buscar_respostas = MagicMock(return_value=[{"r": 1}, {"r": 2}])
        repo._montar_participante = MagicMock(side_effect=[MagicMock(), None])
        mock_db = MagicMock()

        assert len(repo.listar_participantes(mock_db, 1)) == 1
        mock_db.commit.assert_called_once()


@patch("src.formulario.repository.ServicoAuth")
class TestSalvarParticipante:
    def test_cria_quando_nao_existe(self, _auth):
        repo = RepositorioFormulario()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        participante = repo._salvar_participante(mock_db, "Ana", "ana@exemplo.org")

        assert isinstance(participante, Participante)
        assert (participante.nome, participante.email) == ("Ana", "ana@exemplo.org")
        mock_db.add.assert_called_once_with(participante)
        mock_db.flush.assert_called_once()

    def test_atualiza_o_nome_quando_o_email_ja_existe(self, _auth):
        repo = RepositorioFormulario()
        existente = Participante(participante_id=7, nome="Ana", email="ana@exemplo.org")
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existente

        participante = repo._salvar_participante(mock_db, "Ana Souza", "ana@exemplo.org")

        assert participante is existente
        assert participante.nome == "Ana Souza"
        mock_db.flush.assert_not_called()


@patch("src.formulario.repository.ServicoAuth")
class TestGarantirInscricao:
    def test_cria_o_vinculo_quando_nao_existe(self, _auth):
        repo = RepositorioFormulario()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        inscricao = repo._garantir_inscricao(mock_db, 7, 1, "resp-1")

        assert isinstance(inscricao, Inscricao)
        assert (inscricao.participante_id, inscricao.evento_id) == (7, 1)
        assert inscricao.resposta_id == "resp-1"
        mock_db.add.assert_called_once_with(inscricao)

    def test_atualiza_a_resposta_quando_o_vinculo_existe(self, _auth):
        repo = RepositorioFormulario()
        existente = Inscricao(participante_id=7, evento_id=1, resposta_id="antiga")
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existente

        inscricao = repo._garantir_inscricao(mock_db, 7, 1, "nova")

        assert inscricao is existente
        assert inscricao.resposta_id == "nova"

    def test_inscricao_nao_tem_status(self, _auth):
        """Criterio 3 da US09: aprovacao existe apenas no voluntariado."""
        assert not hasattr(Inscricao, "status")


@patch("src.formulario.repository.ServicoAuth")
class TestMontarParticipante:
    def _contexto(self, mock_db, evento_id=1):
        evento = MagicMock()
        evento.evento_id = evento_id
        return {
            "db": mock_db,
            "evento": evento,
            "formulario_id": "part123",
            "id_nome": "q1",
            "id_email": "q2",
        }

    def _resposta(self, nome="Ana", email="ana@exemplo.org", resposta_id="resp-1"):
        return {
            "responseId": resposta_id,
            "answers": {
                "q1": {"textAnswers": {"answers": [{"value": nome}]}},
                "q2": {"textAnswers": {"answers": [{"value": email}]}},
            },
        }

    def test_monta_a_resposta_completa(self, _auth):
        repo = RepositorioFormulario()
        repo._salvar_participante = MagicMock(
            return_value=Participante(participante_id=7, nome="Ana", email="ana@exemplo.org")
        )
        repo._garantir_inscricao = MagicMock()
        mock_db = MagicMock()

        resultado = repo._montar_participante(self._contexto(mock_db), self._resposta())

        assert isinstance(resultado, RespostaInscricaoParticipante)
        assert resultado.participante_id == 7
        assert resultado.evento_id == 1
        assert resultado.nome == "Ana"
        assert resultado.email == "ana@exemplo.org"
        assert resultado.resposta_id == "resp-1"
        assert resultado.link_resposta.endswith("part123/edit#response=resp-1")
        repo._garantir_inscricao.assert_called_once_with(mock_db, 7, 1, "resp-1")

    @pytest.mark.parametrize(
        "resposta",
        [
            pytest.param({"responseId": "r", "answers": {}}, id="sem_nome_e_email"),
            pytest.param({"answers": {}}, id="sem_response_id"),
        ],
    )
    def test_descarta_resposta_incompleta(self, _auth, resposta):
        repo = RepositorioFormulario()
        repo._salvar_participante = MagicMock()

        assert repo._montar_participante(self._contexto(MagicMock()), resposta) is None
        repo._salvar_participante.assert_not_called()
