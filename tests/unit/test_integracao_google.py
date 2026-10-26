"""
O que as chamadas ao Google carregam, e o que elas devolvem.

Estes testes nasceram de uma medicao por mutacao sobre a suite da Sprint 2:
plantando defeitos no codigo da galeria (US07) e da inscricao por formulario
(US09), onze deles **passaram sem nenhum teste reclamar**. Dois grupos:

1. Apagar `requisicao.add_header("Authorization", ...)` nao quebrava teste
   nenhum. Em producao, a chamada sem o cabecalho volta 401 e a galeria fica
   vazia — sem erro visivel na tela, porque a lista vazia e tratada como
   "evento sem fotos".
2. Trocar o retorno por `None` em quatro pontos tambem passava: o id da pasta
   encontrada, o texto extraido da resposta do formulario e o evento buscado.
   Os testes existentes verificavam que o metodo era chamado, nao o que ele
   devolvia.

Cobertura nao mostra isso: as linhas rodavam em 99% dos casos. O que faltava
era assercao.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.drive.service import ServicoDrive
from src.formulario.repository import RepositorioFormulario


def resposta_http(conteudo: dict):
    """Imita o objeto devolvido por urlopen usado como gerenciador de contexto."""
    corpo = MagicMock()
    corpo.read.return_value = json.dumps(conteudo).encode("utf-8")
    corpo.__enter__ = lambda s: s
    corpo.__exit__ = lambda s, *a: False
    return corpo


@pytest.fixture
def servico_drive():
    ServicoDrive.limpar_cache()
    with patch.dict("os.environ", {"GOOGLE_REFRESH_TOKEN": "refresh-123"}), \
         patch("src.drive.service.ServicoAuth"):
        yield ServicoDrive()


class TestTokenNasChamadasAoDrive:
    """
    Toda chamada ao Drive precisa levar o token. Sem o cabecalho, a resposta e
    401 e a galeria aparece vazia, como se o evento nao tivesse fotos.
    """

    def test_busca_de_pasta_envia_o_token(self, servico_drive):
        with patch("src.drive.service.urlopen") as urlopen:
            urlopen.return_value = resposta_http({"files": [{"id": "pasta-1"}]})
            servico_drive._buscar_pasta_id("access-abc", "Acampamento 2026")
        requisicao = urlopen.call_args[0][0]
        assert requisicao.get_header("Authorization") == "Bearer access-abc"

    def test_listagem_de_fotos_envia_o_token(self, servico_drive):
        with patch("src.drive.service.urlopen") as urlopen:
            urlopen.return_value = resposta_http({"files": []})
            servico_drive._buscar_fotos_drive("access-abc", "pasta-1")
        requisicao = urlopen.call_args[0][0]
        assert requisicao.get_header("Authorization") == "Bearer access-abc"

    def test_download_de_imagem_envia_o_token(self, servico_drive):
        servico_drive._obter_token_valido = MagicMock(return_value="access-abc")
        resposta = MagicMock()
        resposta.headers = {"Content-Type": "image/jpeg"}
        resposta.read.return_value = b""
        with patch("src.drive.service.urlopen", return_value=resposta) as urlopen:
            servico_drive.baixar_imagem("arquivo-1")
        requisicao = urlopen.call_args[0][0]
        assert requisicao.get_header("Authorization") == "Bearer access-abc"


class TestRetornoDaBuscaDePasta:

    def test_devolve_o_id_da_pasta_encontrada(self, servico_drive):
        """Devolver None aqui deixa o evento sem galeria, em silencio."""
        with patch("src.drive.service.urlopen") as urlopen:
            urlopen.return_value = resposta_http(
                {"files": [{"id": "pasta-1", "name": "Acampamento"}]}
            )
            assert servico_drive._buscar_pasta_id("tok", "Acampamento") == "pasta-1"

    def test_usa_a_primeira_pasta_quando_o_nome_repete(self, servico_drive):
        with patch("src.drive.service.urlopen") as urlopen:
            urlopen.return_value = resposta_http(
                {"files": [{"id": "pasta-1"}, {"id": "pasta-2"}]}
            )
            assert servico_drive._buscar_pasta_id("tok", "Retiro") == "pasta-1"

    def test_pasta_inexistente_devolve_none(self, servico_drive):
        with patch("src.drive.service.urlopen") as urlopen:
            urlopen.return_value = resposta_http({"files": []})
            assert servico_drive._buscar_pasta_id("tok", "Nao existe") is None


class TestExtracaoDaRespostaDoFormulario:
    """
    O nome e o e-mail do inscrito saem daqui. Devolver None faz a inscricao ser
    descartada por "resposta incompleta" — o participante se inscreve e nunca
    aparece na lista.
    """

    @pytest.fixture
    def repositorio(self):
        with patch("src.formulario.repository.ServicoAuth"):
            return RepositorioFormulario()

    def test_devolve_o_texto_respondido(self, repositorio):
        respostas = {
            "q-nome": {"textAnswers": {"answers": [{"value": "Ana Beatriz"}]}},
        }
        assert repositorio._extrair_texto_resposta(respostas, "q-nome") == "Ana Beatriz"

    def test_usa_a_primeira_resposta_quando_ha_varias(self, repositorio):
        respostas = {
            "q-email": {
                "textAnswers": {"answers": [{"value": "ana@exemplo.com"},
                                            {"value": "outro@exemplo.com"}]}
            },
        }
        assert repositorio._extrair_texto_resposta(respostas, "q-email") == "ana@exemplo.com"

    def test_pergunta_nao_respondida_devolve_none(self, repositorio):
        assert repositorio._extrair_texto_resposta({}, "q-nome") is None

    def test_sem_pergunta_mapeada_devolve_none(self, repositorio):
        respostas = {"q-nome": {"textAnswers": {"answers": [{"value": "Ana"}]}}}
        assert repositorio._extrair_texto_resposta(respostas, None) is None


class TestConsultasMontadas:
    """
    A consulta enviada ao Drive decide o que volta. Trocar `pageSize`, o filtro
    de pasta ou o de imagem nao quebrava teste nenhum, e o efeito aparece so no
    site: album truncado, pasta errada ou arquivo que nao e foto na galeria.
    """

    def test_busca_de_pasta_filtra_por_pasta_e_nome(self, servico_drive):
        url = servico_drive._montar_url_busca_pasta("Acampamento 2026")
        assert "application%2Fvnd.google-apps.folder" in url
        assert "Acampamento" in url
        assert "trashed%3Dfalse" in url

    def test_busca_de_fotos_filtra_por_imagem_dentro_da_pasta(self, servico_drive):
        url = servico_drive._montar_url_busca_fotos("pasta-1")
        assert "pasta-1" in url and "in+parents" in url
        assert "image%2F" in url
        assert "trashed%3Dfalse" in url

    def test_listagem_de_fotos_pede_pagina_grande(self, servico_drive):
        """
        pageSize=100 e o que evita album truncado. Com 1, a galeria mostraria
        uma foto por evento sem erro nenhum.
        """
        assert "pageSize=100" in servico_drive._montar_url_busca_fotos("pasta-1")


class TestMapeamentoDePerguntas:
    """O mapa liga o id da pergunta ao titulo; sem ele, nome e e-mail nao sao achados."""

    @pytest.fixture
    def repositorio(self):
        with patch("src.formulario.repository.ServicoAuth"):
            return RepositorioFormulario()

    def test_mapeia_id_da_pergunta_para_o_titulo(self, repositorio):
        formulario = {
            "items": [
                {"title": "Nome completo",
                 "questionItem": {"question": {"questionId": "q1"}}},
                {"title": "E-mail",
                 "questionItem": {"question": {"questionId": "q2"}}},
            ]
        }
        assert repositorio._mapear_perguntas(formulario) == {
            "q1": "Nome completo",
            "q2": "E-mail",
        }

    def test_item_sem_pergunta_fica_de_fora(self, repositorio):
        """Secao e texto solto do formulario nao tem questionId."""
        formulario = {
            "items": [
                {"title": "DADOS DO LÍDER"},
                {"title": "Nome", "questionItem": {"question": {"questionId": "q1"}}},
            ]
        }
        assert repositorio._mapear_perguntas(formulario) == {"q1": "Nome"}

    def test_formulario_vazio_devolve_mapa_vazio(self, repositorio):
        assert repositorio._mapear_perguntas({}) == {}


class TestBuscaDoEvento:

    @pytest.fixture
    def repositorio(self):
        with patch("src.formulario.repository.ServicoAuth"):
            return RepositorioFormulario()

    def test_devolve_o_evento_encontrado(self, repositorio):
        evento = MagicMock(evento_id=7)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = evento
        assert repositorio._buscar_evento(db, 7) is evento

    def test_evento_inexistente_levanta_erro(self, repositorio):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError, match="Evento"):
            repositorio._buscar_evento(db, 99)
