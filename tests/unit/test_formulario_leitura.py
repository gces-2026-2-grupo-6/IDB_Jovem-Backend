"""
Testes da leitura de formulario do Google.

Os dois defeitos travados aqui foram encontrados na reuniao de validacao com a
cliente em 23/11/2026, e os dois falhavam em silencio: nenhuma resposta era
gravada e a tela mostrava lista vazia, sem erro.

Este modulo e puro de proposito — nao importa banco nem rede —, entao estes
testes rodam sozinhos e rapido.
"""

import pytest

from src.formulario.leitura import (
    TITULOS_EMAIL,
    TITULOS_NOME,
    extrair_formulario_id,
    localizar_id_pergunta,
    normalizar_titulo,
)

ID_REAL = "1KlgPPSxOr2rJEWq4CwGSmvNB0qYgB_QKBKcUbXPDpCM"


class TestExtrairFormularioId:
    """O link de edicao e o unico que a API do Google aceita."""

    def test_link_de_edicao_devolve_o_id(self):
        link = f"https://docs.google.com/forms/d/{ID_REAL}/edit"
        assert extrair_formulario_id(link) == ID_REAL

    def test_link_de_edicao_com_fragmento_ou_parametro(self):
        link = f"https://docs.google.com/forms/d/{ID_REAL}/edit#responses"
        assert extrair_formulario_id(link) == ID_REAL

    def test_link_de_compartilhar_nao_vira_a_letra_e(self):
        """O defeito original: `/forms/d/e/` passava e o id extraido era "e".

        A chamada seguia para `forms.googleapis.com/v1/forms/e`, falhava, e
        nada aparecia na tela.
        """
        link = (
            "https://docs.google.com/forms/d/e/"
            "1FAIpQLSeAY2d1_DbzV-hDHeBilNSB7ZK36vE3FvI2ZhJacyYHl34PQg/viewform"
        )
        with pytest.raises(ValueError) as erro:
            extrair_formulario_id(link)

        assert "e" != str(erro.value)
        assert "/edit" in str(erro.value)
        assert "compartilhar" in str(erro.value).lower()

    def test_link_de_compartilhar_com_parametro(self):
        link = (
            "https://docs.google.com/forms/d/e/1FAIpQLSeAY2d1/viewform"
            "?fbzx=-333614439256918245"
        )
        with pytest.raises(ValueError):
            extrair_formulario_id(link)

    def test_link_encurtado_e_recusado_com_explicacao(self):
        with pytest.raises(ValueError) as erro:
            extrair_formulario_id("https://forms.gle/abc123")

        assert "/edit" in str(erro.value)

    @pytest.mark.parametrize("link", ["", "   ", None])
    def test_link_vazio(self, link):
        with pytest.raises(ValueError):
            extrair_formulario_id(link)

    def test_link_que_nao_e_do_forms(self):
        with pytest.raises(ValueError) as erro:
            extrair_formulario_id("https://example.com/qualquer-coisa")

        assert "/edit" in str(erro.value)


class TestNormalizarTitulo:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("Nome", "nome"),
            ("  Nome  ", "nome"),
            ("E-mail", "e mail"),
            ("E-mail:", "e mail"),
            ("Email *", "email"),
            ("Nome  Completo", "nome completo"),
            ("Endereço de e-mail", "endereco de e mail"),
            ("", ""),
        ],
    )
    def test_formas_equivalentes(self, entrada, esperado):
        assert normalizar_titulo(entrada) == esperado


class TestLocalizarIdPergunta:
    """O defeito que impediu a inscricao de aparecer: so "Nome" e "Email"
    exatos eram reconhecidos."""

    def test_titulos_exatos_continuam_funcionando(self):
        mapa = {"q1": "Nome", "q2": "Email"}
        assert localizar_id_pergunta(mapa, TITULOS_NOME) == "q1"
        assert localizar_id_pergunta(mapa, TITULOS_EMAIL) == "q2"

    @pytest.mark.parametrize("titulo", ["E-mail", "e-mail", "E-MAIL", "Seu e-mail", "E-mail:"])
    def test_variacoes_de_email_sao_reconhecidas(self, titulo):
        mapa = {"q1": "Nome", "q2": titulo}
        assert localizar_id_pergunta(mapa, TITULOS_EMAIL) == "q2"

    @pytest.mark.parametrize(
        "titulo", ["Nome completo", "Seu nome", "Nome e sobrenome", "nome completo"]
    )
    def test_variacoes_de_nome_sao_reconhecidas(self, titulo):
        mapa = {"q1": titulo, "q2": "Email"}
        assert localizar_id_pergunta(mapa, TITULOS_NOME) == "q1"

    def test_nome_da_igreja_nao_e_confundido_com_o_nome_da_pessoa(self):
        """O formulario de lideres (US10) tem "Nome da igreja" e "Nome do
        pastor". Casar por "contem" pegaria o campo errado."""
        mapa = {"q1": "Nome da igreja", "q2": "Nome completo", "q3": "E-mail"}
        assert localizar_id_pergunta(mapa, TITULOS_NOME) == "q2"

    def test_sem_campo_reconhecivel_devolve_none(self):
        mapa = {"q1": "Como voce conheceu o evento?", "q2": "Camiseta"}
        assert localizar_id_pergunta(mapa, TITULOS_NOME) is None
        assert localizar_id_pergunta(mapa, TITULOS_EMAIL) is None

    def test_a_ordem_da_lista_decide_a_prioridade(self):
        mapa = {"q1": "Nome completo", "q2": "Nome"}
        assert localizar_id_pergunta(mapa, TITULOS_NOME) == "q2"
