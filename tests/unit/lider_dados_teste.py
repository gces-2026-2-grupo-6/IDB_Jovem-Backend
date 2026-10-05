"""Dados de teste reutilizáveis para o módulo lider (US05).

Cobrem os cenários exigidos pela US05: líder atual, diretor anterior
nacional e diretor anterior estrangeiro, com perfil completo (foto,
região, mini-biografia e redes sociais) em pelo menos um exemplo de
cada categoria. Todos os dados são fictícios.
"""
from src.lider.model import Lider


def lider_atual_brasileiro(**overrides) -> Lider:
    dados = dict(
        lider_id=1,
        nome="Ana Souza",
        cargo="Coordenadora Geral",
        imagem_url="https://exemplo.org/fotos/ana-souza.jpg",
        is_antigo=False,
        ordem=1,
        regiao="Sudeste",
        mini_biografia="Atua na coordenação geral do ministério jovem desde 2022.",
        redes_sociais={
            "instagram": "https://instagram.com/ana.souza.exemplo",
            "linkedin": "https://linkedin.com/in/ana-souza-exemplo",
        },
    )
    dados.update(overrides)
    return Lider(**dados)


def diretor_anterior_brasileiro(**overrides) -> Lider:
    dados = dict(
        lider_id=2,
        nome="Carlos Pereira",
        cargo="Ex-Diretor Nacional",
        imagem_url="https://exemplo.org/fotos/carlos-pereira.jpg",
        is_antigo=True,
        ordem=10,
        regiao="Nordeste",
        mini_biografia="Diretor nacional entre 2015 e 2020.",
        redes_sociais={
            "instagram": "https://instagram.com/carlos.pereira.exemplo",
        },
    )
    dados.update(overrides)
    return Lider(**dados)


def diretor_anterior_estrangeiro(**overrides) -> Lider:
    dados = dict(
        lider_id=3,
        nome="Maria Fernández",
        cargo="Ex-Diretora Regional",
        imagem_url="https://exemplo.org/fotos/maria-fernandez.jpg",
        is_antigo=True,
        ordem=11,
        regiao="América Latina - Argentina",
        mini_biografia=(
            "Liderou a expansão do ministério jovem na Argentina entre 2010 e 2016."
        ),
        redes_sociais={
            "instagram": "https://instagram.com/maria.fernandez.exemplo",
            "linkedin": "https://linkedin.com/in/maria-fernandez-exemplo",
        },
    )
    dados.update(overrides)
    return Lider(**dados)


def lideres_exemplo() -> list[Lider]:
    """Conjunto completo, útil para popular um banco de teste local."""
    return [
        lider_atual_brasileiro(),
        diretor_anterior_brasileiro(),
        diretor_anterior_estrangeiro(),
    ]
