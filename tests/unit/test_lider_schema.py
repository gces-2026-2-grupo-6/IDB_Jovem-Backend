import pytest
from pydantic import ValidationError

from src.lider.schema import SolicitacaoLider, RespostaLider
from tests.unit.lider_dados_teste import (
    lider_atual_brasileiro,
    diretor_anterior_estrangeiro,
)


PERFIL_COMPLETO = {
    "nome": "Ana Souza",
    "cargo": "Coordenadora Geral",
    "imagem_url": "https://exemplo.org/fotos/ana-souza.jpg",
    "is_antigo": False,
    "ordem": 1,
    "regiao": "Sudeste",
    "mini_biografia": "Atua na coordenação geral do ministério jovem desde 2022.",
    "redes_sociais": {
        "instagram": "https://instagram.com/ana.souza.exemplo",
        "linkedin": "https://linkedin.com/in/ana-souza-exemplo",
    },
}


def test_aceita_perfil_completo():
    lider = SolicitacaoLider(**PERFIL_COMPLETO)

    assert lider.regiao == "Sudeste"
    assert lider.mini_biografia.startswith("Atua na coordenação")
    assert lider.redes_sociais == PERFIL_COMPLETO["redes_sociais"]


def test_campos_de_perfil_sao_opcionais():
    lider = SolicitacaoLider(nome="Ana Souza", cargo="Coordenadora Geral")

    assert lider.regiao is None
    assert lider.mini_biografia is None
    assert lider.redes_sociais is None


def test_is_antigo_e_falso_por_padrao():
    assert SolicitacaoLider(nome="Ana", cargo="Líder").is_antigo is False


def test_is_antigo_respeita_a_marcacao_manual():
    assert SolicitacaoLider(nome="Carlos", cargo="Diretor", is_antigo=True).is_antigo is True


@pytest.mark.parametrize("valor", ["", "   "])
@pytest.mark.parametrize("campo", ["regiao", "mini_biografia"])
def test_texto_vazio_vira_nulo(campo, valor):
    lider = SolicitacaoLider(nome="Ana", cargo="Líder", **{campo: valor})
    assert getattr(lider, campo) is None


def test_texto_e_aparado():
    lider = SolicitacaoLider(nome="Ana", cargo="Líder", regiao="  Sudeste  ")
    assert lider.regiao == "Sudeste"


@pytest.mark.parametrize("valor", [None, "", {}])
def test_redes_sociais_ausentes_viram_nulo(valor):
    lider = SolicitacaoLider(nome="Ana", cargo="Líder", redes_sociais=valor)
    assert lider.redes_sociais is None


def test_redes_sociais_apara_espacos_e_descarta_links_vazios():
    lider = SolicitacaoLider(
        nome="Ana",
        cargo="Líder",
        redes_sociais={
            " instagram ": " https://instagram.com/ana ",
            "linkedin": "",
            "youtube": None,
        },
    )
    assert lider.redes_sociais == {"instagram": "https://instagram.com/ana"}


def test_redes_sociais_so_com_links_vazios_vira_nulo():
    lider = SolicitacaoLider(nome="Ana", cargo="Líder", redes_sociais={"instagram": "  "})
    assert lider.redes_sociais is None


@pytest.mark.parametrize(
    "valor",
    [
        pytest.param("@ana, youtube.com/ana", id="texto_livre"),
        pytest.param(["https://instagram.com/ana"], id="lista"),
        pytest.param(123, id="numero"),
    ],
)
def test_redes_sociais_recusa_o_que_nao_e_objeto(valor):
    with pytest.raises(ValidationError, match="objeto JSON"):
        SolicitacaoLider(nome="Ana", cargo="Líder", redes_sociais=valor)


def test_redes_sociais_recusa_link_que_nao_e_texto():
    with pytest.raises(ValidationError, match="deve ser um texto"):
        SolicitacaoLider(nome="Ana", cargo="Líder", redes_sociais={"instagram": 42})


def test_redes_sociais_recusa_nome_de_rede_vazio():
    with pytest.raises(ValidationError, match="nome de cada rede"):
        SolicitacaoLider(nome="Ana", cargo="Líder", redes_sociais={" ": "https://x.com/ana"})


def test_campos_desconhecidos_sao_ignorados():
    lider = SolicitacaoLider(nome="Ana", cargo="Líder", bio="texto", gestao="2020 - 2023")
    dados = lider.model_dump()

    assert "bio" not in dados
    assert "gestao" not in dados


def test_resposta_expoe_perfil_a_partir_do_modelo():
    resposta = RespostaLider.model_validate(lider_atual_brasileiro())

    assert resposta.lider_id == 1
    assert resposta.regiao == "Sudeste"
    assert resposta.mini_biografia
    assert resposta.redes_sociais["instagram"].startswith("https://instagram.com/")


def test_resposta_serializa_redes_sociais_como_objeto():
    json_resposta = RespostaLider.model_validate(diretor_anterior_estrangeiro()).model_dump(mode="json")

    assert json_resposta["is_antigo"] is True
    assert isinstance(json_resposta["redes_sociais"], dict)
    assert set(json_resposta["redes_sociais"]) == {"instagram", "linkedin"}
