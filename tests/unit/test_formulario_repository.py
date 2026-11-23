import pytest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError
from src.formulario.repository import RepositorioFormulario
from src.formulario.schema import RespostaInscricaoFormulario


class TestRepositorioFormulario:
    @patch.dict("os.environ", {"GOOGLE_REFRESH_TOKEN": ""})
    @patch("src.formulario.repository.ServicoAuth")
    def test_obter_token_sem_refresh(self, mock_auth_class):
        repo = RepositorioFormulario()
        repo.refresh_token = None
        with pytest.raises(RuntimeError, match="GOOGLE_REFRESH_TOKEN nao configurado"):
            repo._obter_token_valido()

    @patch.dict("os.environ", {"GOOGLE_REFRESH_TOKEN": "token-123"})
    @patch("src.formulario.repository.ServicoAuth")
    def test_obter_token_sucesso(self, mock_auth_class):
        mock_auth = MagicMock()
        mock_creds = MagicMock()
        mock_creds.token = "access-token"
        mock_auth.obter_credenciais_validas.return_value = mock_creds
        mock_auth_class.return_value = mock_auth

        repo = RepositorioFormulario()
        resultado = repo._obter_token_valido()
        assert resultado == "access-token"

    @patch.dict("os.environ", {"GOOGLE_REFRESH_TOKEN": "token-123"})
    @patch("src.formulario.repository.ServicoAuth")
    def test_obter_token_falha(self, mock_auth_class):
        mock_auth = MagicMock()
        mock_auth.obter_credenciais_validas.side_effect = Exception("Erro")
        mock_auth_class.return_value = mock_auth

        repo = RepositorioFormulario()
        with pytest.raises(RuntimeError, match="Falha automatica ao renovar credenciais"):
            repo._obter_token_valido()

    # `_extrair_formulario_id_link` saiu do repositorio: a logica virou
    # `leitura.extrair_formulario_id`, que recusa cada formato errado com a sua
    # mensagem em vez de devolver None. Coberta em test_formulario_leitura.py.

    @patch("src.formulario.repository.ServicoAuth")
    def test_definir_formulario_id_valido(self, mock_auth_class):
        repo = RepositorioFormulario()
        resultado = repo._definir_formulario_id(
            "https://docs.google.com/forms/d/abc123/edit"
        )
        assert resultado == "abc123"

    @patch("src.formulario.repository.ServicoAuth")
    def test_definir_formulario_id_invalido(self, mock_auth_class):
        repo = RepositorioFormulario()
        with pytest.raises(ValueError, match="Nao reconheci esse link"):
            repo._definir_formulario_id("http://example.com")

    @patch("src.formulario.repository.ServicoAuth")
    def test_montar_link_resposta(self, mock_auth_class):
        repo = RepositorioFormulario()
        resultado = repo._montar_link_resposta("form-id", "resp-id")
        assert "form-id" in resultado
        assert "resp-id" in resultado

    @patch("src.formulario.repository.ServicoAuth")
    def test_montar_requisicao(self, mock_auth_class):
        repo = RepositorioFormulario()
        req = repo._montar_requisicao("http://example.com", "token")
        assert req.get_header("Authorization") == "Bearer token"

    @patch("src.formulario.repository.urlopen")
    @patch("src.formulario.repository.ServicoAuth")
    def test_buscar_json_sucesso(self, mock_auth_class, mock_urlopen):
        import json
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"key": "value"}).encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        repo = RepositorioFormulario()
        resultado = repo._buscar_json("http://example.com", "token", "Erro")
        assert resultado["key"] == "value"

    @patch("src.formulario.repository.urlopen")
    @patch("src.formulario.repository.ServicoAuth")
    def test_buscar_json_http_error(self, mock_auth_class, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="http://test.com", code=500, msg="Error", hdrs=None, fp=None
        )
        repo = RepositorioFormulario()
        with pytest.raises(RuntimeError, match="Erro de teste"):
            repo._buscar_json("http://example.com", "token", "Erro de teste")

    @patch("src.formulario.repository.ServicoAuth")
    def test_buscar_formulario_sucesso(self, mock_auth_class):
        repo = RepositorioFormulario()
        repo._buscar_json = MagicMock(return_value={"id": "123"})
        resultado = repo._buscar_formulario("token", "123")
        assert resultado == {"id": "123"}
        repo._buscar_json.assert_called_once_with(
            "https://forms.googleapis.com/v1/forms/123", "token", "Falha ao buscar formulario no Google Forms"
        )

    @patch("src.formulario.repository.ServicoAuth")
    def test_buscar_respostas_sucesso(self, mock_auth_class):
        repo = RepositorioFormulario()
        repo._buscar_json = MagicMock(return_value={"responses": [{"id": "r1"}]})
        resultado = repo._buscar_respostas("token", "123")
        assert resultado == [{"id": "r1"}]
        repo._buscar_json.assert_called_once_with(
            "https://forms.googleapis.com/v1/forms/123/responses", "token", "Falha ao buscar respostas no Google Forms"
        )

    @patch("src.formulario.repository.ServicoAuth")
    def test_buscar_respostas_vazio(self, mock_auth_class):
        repo = RepositorioFormulario()
        repo._buscar_json = MagicMock(return_value={})
        resultado = repo._buscar_respostas("token", "123")
        assert resultado == []

    @patch("src.formulario.repository.ServicoAuth")
    def test_mapear_perguntas(self, mock_auth_class):
        repo = RepositorioFormulario()
        formulario = {
            "items": [
                {
                    "title": "Nome",
                    "questionItem": {
                        "question": {"questionId": "q1"}
                    }
                },
                {
                    "title": "Email",
                    "questionItem": {
                        "question": {"questionId": "q2"}
                    }
                },
            ]
        }
        mapa = repo._mapear_perguntas(formulario)
        assert mapa["q1"] == "Nome"
        assert mapa["q2"] == "Email"

    @patch("src.formulario.repository.ServicoAuth")
    def test_mapear_perguntas_sem_items(self, mock_auth_class):
        repo = RepositorioFormulario()
        mapa = repo._mapear_perguntas({})
        assert mapa == {}

    # `_localizar_id_pergunta` saiu do repositorio: virou
    # `leitura.localizar_id_pergunta`, que aceita uma lista de titulos em vez de
    # um so. Coberta em test_formulario_leitura.py.

    @patch("src.formulario.repository.ServicoAuth")
    def test_extrair_texto_resposta_sucesso(self, mock_auth_class):
        repo = RepositorioFormulario()
        respostas = {
            "q1": {"textAnswers": {"answers": [{"value": "João"}]}}
        }
        resultado = repo._extrair_texto_resposta(respostas, "q1")
        assert resultado == "João"

    @patch("src.formulario.repository.ServicoAuth")
    def test_extrair_texto_resposta_sem_pergunta_id(self, mock_auth_class):
        repo = RepositorioFormulario()
        resultado = repo._extrair_texto_resposta({}, None)
        assert resultado is None

    @patch("src.formulario.repository.ServicoAuth")
    def test_extrair_texto_resposta_sem_resposta(self, mock_auth_class):
        repo = RepositorioFormulario()
        resultado = repo._extrair_texto_resposta({}, "q1")
        assert resultado is None

    @patch("src.formulario.repository.ServicoAuth")
    def test_extrair_texto_resposta_sem_answers(self, mock_auth_class):
        repo = RepositorioFormulario()
        respostas = {"q1": {"textAnswers": {"answers": []}}}
        resultado = repo._extrair_texto_resposta(respostas, "q1")
        assert resultado is None

    @patch("src.formulario.repository.ServicoAuth")
    def test_buscar_evento_sucesso(self, mock_auth_class):
        repo = RepositorioFormulario()
        mock_db = MagicMock()
        mock_evento = MagicMock()
        mock_db.query().filter().first.return_value = mock_evento
        resultado = repo._buscar_evento(mock_db, 1)
        assert resultado == mock_evento

    @patch("src.formulario.repository.ServicoAuth")
    def test_buscar_evento_nao_encontrado(self, mock_auth_class):
        repo = RepositorioFormulario()
        mock_db = MagicMock()
        mock_db.query().filter().first.return_value = None
        with pytest.raises(ValueError, match="Evento nao encontrado"):
            repo._buscar_evento(mock_db, 1)

    @patch("src.formulario.repository.ServicoAuth")
    def test_salvar_voluntario_novo(self, mock_auth_class):
        repo = RepositorioFormulario()
        mock_db = MagicMock()
        mock_db.query().filter().first.return_value = None

        resultado = repo._salvar_voluntario(mock_db, "João", "joao@email.com")
        mock_db.add.assert_called()
        mock_db.flush.assert_called_once()

    @patch("src.formulario.repository.ServicoAuth")
    def test_salvar_voluntario_existente(self, mock_auth_class):
        repo = RepositorioFormulario()
        mock_db = MagicMock()
        mock_voluntario = MagicMock()
        mock_voluntario.nome = "Antigo"
        mock_db.query().filter().first.return_value = mock_voluntario

        resultado = repo._salvar_voluntario(mock_db, "Novo", "joao@email.com")
        assert resultado.nome == "Novo"
        mock_db.add.assert_called_once_with(mock_voluntario)

    @patch("src.formulario.repository.ServicoAuth")
    def test_garantir_trabalho_novo(self, mock_auth_class):
        repo = RepositorioFormulario()
        mock_db = MagicMock()
        mock_db.query().filter().first.return_value = None

        resultado = repo._garantir_trabalho(mock_db, 1, 2, "resp-id")
        mock_db.add.assert_called_once()
        assert resultado.status == "pendente"

    @patch("src.formulario.repository.ServicoAuth")
    def test_garantir_trabalho_existente(self, mock_auth_class):
        repo = RepositorioFormulario()
        mock_db = MagicMock()
        mock_trabalho = MagicMock()
        mock_trabalho.resposta_id = "old-resp"
        mock_db.query().filter().first.return_value = mock_trabalho

        resultado = repo._garantir_trabalho(mock_db, 1, 2, "new-resp")
        assert resultado.resposta_id == "new-resp"

    @patch("src.formulario.repository.ServicoAuth")
    def test_montar_inscricao_sucesso(self, mock_auth_class):
        repo = RepositorioFormulario()
        mock_db = MagicMock()
        mock_voluntario = MagicMock()
        mock_voluntario.voluntario_id = 1
        mock_voluntario.nome = "João"
        mock_voluntario.email = "joao@email.com"
        mock_db.query().filter().first.return_value = None

        repo._salvar_voluntario = MagicMock(return_value=mock_voluntario)
        mock_trabalho = MagicMock()
        mock_trabalho.status = "pendente"
        repo._garantir_trabalho = MagicMock(return_value=mock_trabalho)

        mock_evento = MagicMock()
        mock_evento.evento_id = 2

        contexto = {
            "db": mock_db,
            "evento": mock_evento,
            "formulario_id": "form-id",
            "id_nome": "q1",
            "id_email": "q2",
        }
        resposta = {
            "responseId": "resp-1",
            "answers": {
                "q1": {"textAnswers": {"answers": [{"value": "João"}]}},
                "q2": {"textAnswers": {"answers": [{"value": "joao@email.com"}]}},
            }
        }

        resultado = repo._montar_inscricao(contexto, resposta)
        assert resultado is not None
        assert resultado.nome == "João"

    @patch("src.formulario.repository.ServicoAuth")
    def test_montar_inscricao_sem_nome(self, mock_auth_class):
        repo = RepositorioFormulario()
        contexto = {
            "db": MagicMock(),
            "evento": MagicMock(),
            "formulario_id": "form-id",
            "id_nome": "q1",
            "id_email": "q2",
        }
        resposta = {
            "responseId": "resp-1",
            "answers": {
                "q2": {"textAnswers": {"answers": [{"value": "joao@email.com"}]}},
            }
        }

        resultado = repo._montar_inscricao(contexto, resposta)
        assert resultado is None

    @patch("src.formulario.repository.ServicoAuth")
    def test_montar_inscricao_sem_response_id(self, mock_auth_class):
        repo = RepositorioFormulario()
        contexto = {
            "db": MagicMock(),
            "evento": MagicMock(),
            "formulario_id": "form-id",
            "id_nome": "q1",
            "id_email": "q2",
        }
        resposta = {
            "responseId": "",
            "answers": {
                "q1": {"textAnswers": {"answers": [{"value": "João"}]}},
                "q2": {"textAnswers": {"answers": [{"value": "joao@email.com"}]}},
            }
        }

        resultado = repo._montar_inscricao(contexto, resposta)
        assert resultado is None

    @patch("src.formulario.repository.ServicoAuth")
    def test_listar_inscricoes_sucesso(self, mock_auth_class):
        repo = RepositorioFormulario()
        repo._obter_token_valido = MagicMock(return_value="token")

        mock_evento = MagicMock()
        mock_evento.evento_id = 1
        mock_evento.formulario_link = "https://docs.google.com/forms/d/abc123/edit"
        repo._buscar_evento = MagicMock(return_value=mock_evento)

        repo._buscar_formulario = MagicMock(return_value={"items": []})
        repo._buscar_respostas = MagicMock(return_value=[])

        mock_db = MagicMock()
        resultado = repo.listar_inscricoes(mock_db, 1)
        assert resultado == []
        mock_db.commit.assert_called_once()

    @patch("src.formulario.repository.ServicoAuth")
    def test_listar_inscricoes_sem_formulario(self, mock_auth_class):
        repo = RepositorioFormulario()
        repo._obter_token_valido = MagicMock(return_value="token")

        mock_evento = MagicMock()
        mock_evento.formulario_link = None
        repo._buscar_evento = MagicMock(return_value=mock_evento)

        mock_db = MagicMock()
        with pytest.raises(ValueError, match="Evento sem formulario configurado"):
            repo.listar_inscricoes(mock_db, 1)

    @patch("src.formulario.repository.ServicoAuth")
    def test_listar_inscricoes_com_respostas(self, mock_auth_class):
        repo = RepositorioFormulario()
        repo._obter_token_valido = MagicMock(return_value="token")

        mock_evento = MagicMock()
        mock_evento.evento_id = 1
        mock_evento.formulario_link = "https://docs.google.com/forms/d/abc123/edit"
        repo._buscar_evento = MagicMock(return_value=mock_evento)

        repo._buscar_formulario = MagicMock(return_value={"items": []})
        repo._buscar_respostas = MagicMock(return_value=[{"resp": "1"}, {"resp": "2"}])
        repo._mapear_perguntas = MagicMock(return_value={"q1": "Nome", "q2": "Email"})
        repo._localizar_id_pergunta = MagicMock(side_effect=["q1", "q2"])
        
        mock_inscricao = MagicMock()
        repo._montar_inscricao = MagicMock(side_effect=[mock_inscricao, None])

        mock_db = MagicMock()
        resultado = repo.listar_inscricoes(mock_db, 1)
        assert len(resultado) == 1
        mock_db.commit.assert_called_once()
