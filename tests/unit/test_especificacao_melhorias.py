"""
Especificacao antecipada das melhorias validadas com a cliente em 06/10/2026.

As regras abaixo entraram no backlog de melhorias e ainda nao tem codigo. Em
vez de esperar a entrega do trio para so entao escrever teste, cada regra fica
registrada aqui de uma das duas formas:

* `xfail(strict=True)` para o que o sistema **ainda nao faz** ("deve recusar",
  "deve publicar"). Hoje falha como esperado e nao suja a suite. No dia em que
  a implementacao entrar, o pytest acusa `XPASS(strict)` e obriga quem
  implementou a remover o marcador, mantendo o teste como regressao. Se a
  entrega vier **diferente** do que a cliente pediu, o teste continua falhando
  e isso aparece na revisao da PR.
* teste normal, verde hoje, para o que o sistema **ja permite e nao pode
  deixar de permitir**. Sao a metade que importa: hoje nao existe validacao
  nenhuma de cargo, entao "dois diretores regionais de regioes diferentes" ja
  passa. Registrar isso agora e o que impede a implementacao ingenua — unicidade
  so por nome do cargo — de entrar sem ninguem perceber (RF58).

Nomes de campo: nenhum foi combinado com o trio ainda, entao cada regra aceita
qualquer um dos nomes plausiveis (conjuntos `CAMPOS_*`). Quem implementar com
um nome fora da lista acrescenta o nome ao conjunto na propria PR — e a revisao
fica sabendo que o contrato publico da API mudou.

Regras cobertas:

    US19 / RF60  evento online ou presencial (prioridade especial da cliente)
    US14         evento cancelado ou adiado
    US11         download de toda foto, video e documento do site
    US10 / RF58  cargo unico considerando a abrangencia
    US23 / RF59  calendario guardando os eventos que ja ocorreram

Fora daqui de proposito: a US10 "dois links fixados na home". Os dois links
sao conteudo da pagina inicial, nenhuma rota os serve e inventar uma aqui
amarraria o trio a uma API que ninguem decidiu. A verificacao dela e no
front-end.
"""

from datetime import date, datetime
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src.calendario.service import ServicoCalendario
from src.drive.schema import RespostaDrive
from src.evento.schema import (
    RespostaEvento,
    RespostaItemGaleria,
    SolicitacaoEvento,
    TipoEvento,
)
from src.lider.schema import SolicitacaoLider
from src.lider.service import ServicoLider
from src.main import app
from src.lider.model import Lider

PENDENTE = (
    "Regra aceita no backlog de melhorias (reuniao de 06/10/2026) e ainda sem "
    "implementacao. Quando entrar, remova o xfail e mantenha o teste."
)

# Nomes aceitos para cada campo novo. Acrescente o nome escolhido na PR que
# implementar a regra.
CAMPOS_MODALIDADE = {"modalidade", "formato", "is_online", "online", "tipo_modalidade"}
CAMPOS_SITUACAO = {"situacao", "status", "estado", "situacao_evento"}
CAMPOS_DOWNLOAD = {"url_download", "link_download", "download_url", "download"}

VALORES_ONLINE = ("online", "Online", "ONLINE", True)

EVENTO_BASE = {
    "nome": "Congresso Nacional de Adolescentes 2027",
    "tipo_evento": TipoEvento.CONFERENCIA,
    "data_inicio": datetime(2027, 3, 1, 9, 0),
    "data_fim": datetime(2027, 3, 1, 18, 0),
}

EVENTO_PRESENCIAL = {**EVENTO_BASE, "local_latitude": -15.79, "local_longitude": -47.88}

# A implementacao pode recusar na camada de servico (ValueError) ou direto no
# controller (HTTPException 409). As duas formas satisfazem a regra.
RECUSAS_ACEITAS = (ValueError, HTTPException)


def campos_encontrados(modelo, candidatos) -> list[str]:
    """Quais dos nomes aceitos o modelo realmente publica."""
    return sorted(set(modelo.model_fields) & candidatos)


class RepositorioLiderEmMemoria:
    """
    Mesma interface do `RepositorioLider`, sem banco.

    Um `MagicMock` nao serve aqui: ele devolve objeto para qualquer consulta,
    entao uma verificacao de cargo recem-implementada enxergaria duplicata em
    todo cadastro e os testes verdes abaixo quebrariam sem motivo.
    """

    def __init__(self):
        self.lideres: list[Lider] = []
        self._proximo_id = 1

    def salvar(self, lider: Lider) -> Lider:
        if lider.lider_id is None:
            lider.lider_id = self._proximo_id
            self._proximo_id += 1
            self.lideres.append(lider)
        return lider

    def buscar_todos(self) -> list[Lider]:
        return list(self.lideres)

    def buscar_lideres_atuais(self) -> list[Lider]:
        return [lider for lider in self.lideres if not lider.is_antigo]

    def buscar_diretores_anteriores(self) -> list[Lider]:
        return [lider for lider in self.lideres if lider.is_antigo]

    def buscar_por_id(self, lider_id: int) -> Lider | None:
        return next((l for l in self.lideres if l.lider_id == lider_id), None)

    def deletar(self, lider: Lider) -> None:
        self.lideres.remove(lider)


@pytest.fixture
def servico_lider() -> ServicoLider:
    return ServicoLider(RepositorioLiderEmMemoria())


@pytest.fixture
def servico_calendario() -> ServicoCalendario:
    with patch("src.calendario.service.ServicoAuth"):
        return ServicoCalendario()


class TestModalidadeDoEvento:
    """
    US19, a prioridade que a cliente destacou: hoje todo cadastro de evento
    exige endereco e coordenadas. Evento online nao tem endereco, e a decisao
    registrada foi marcar a modalidade no proprio cadastro de evento — online
    desobriga o endereco, presencial continua como esta.
    """

    def test_resposta_de_evento_publica_a_modalidade(self):
        assert campos_encontrados(RespostaEvento, CAMPOS_MODALIDADE), (
            "O front precisa saber se o evento e online para decidir entre mostrar "
            f"endereco ou link de acesso. Nomes aceitos: {sorted(CAMPOS_MODALIDADE)}."
        )

    def test_evento_online_e_aceito_sem_coordenadas(self):
        campos = campos_encontrados(SolicitacaoEvento, CAMPOS_MODALIDADE)
        assert campos, f"Cadastro sem campo de modalidade. Aceitos: {sorted(CAMPOS_MODALIDADE)}."

        for valor in VALORES_ONLINE:
            try:
                SolicitacaoEvento(**EVENTO_BASE, **{campos[0]: valor})
            except ValidationError:
                continue
            return

        pytest.fail(
            f"Evento marcado como online em '{campos[0]}' continua exigindo "
            "coordenadas. A regra e: online desobriga o endereco."
        )

    def test_evento_presencial_continua_exigindo_coordenadas(self):
        """
        O outro lado da regra, e verde hoje. Se a implementacao da modalidade
        tornar as coordenadas opcionais para todo mundo, este teste quebra.
        """
        with pytest.raises(ValidationError):
            SolicitacaoEvento(**EVENTO_BASE)


class TestSituacaoDoEvento:
    """
    US14: evento pode ser cancelado ou adiado, e nos dois casos o registro
    continua no site — nao e exclusao. Hoje nao existe onde guardar isso.
    """

    def test_resposta_de_evento_publica_a_situacao(self):
        assert campos_encontrados(RespostaEvento, CAMPOS_SITUACAO), (
            "Sem esse campo o site nao tem como avisar que o evento foi cancelado "
            f"ou adiado. Nomes aceitos: {sorted(CAMPOS_SITUACAO)}."
        )

    @pytest.mark.parametrize("situacao", ["cancelado", "adiado"])
    def test_cadastro_aceita_marcar_o_evento(self, situacao):
        campos = campos_encontrados(SolicitacaoEvento, CAMPOS_SITUACAO)
        assert campos, f"Cadastro sem campo de situacao. Aceitos: {sorted(CAMPOS_SITUACAO)}."

        evento = SolicitacaoEvento(**EVENTO_PRESENCIAL, **{campos[0]: situacao})
        assert getattr(evento, campos[0]) is not None, (
            f"O valor '{situacao}' foi descartado na validacao."
        )


class TestDownloadDeMaterial:
    """
    US11: toda foto, video e documento publicado pelo superadmin pode ser
    baixado por qualquer visitante. Hoje a galeria publica apenas
    `url_visualizacao`, que serve para exibir, nao para baixar.
    """

    def test_galeria_do_evento_publica_link_de_download(self):
        assert campos_encontrados(RespostaDrive, CAMPOS_DOWNLOAD), (
            "`/evento/{id}/galeria` nao oferece como baixar o arquivo. "
            f"Nomes aceitos: {sorted(CAMPOS_DOWNLOAD)}."
        )

    def test_galeria_geral_publica_link_de_download(self):
        assert campos_encontrados(RespostaItemGaleria, CAMPOS_DOWNLOAD), (
            "`/evento/galerias/todas` alimenta a galeria da home e tambem precisa "
            f"do link. Nomes aceitos: {sorted(CAMPOS_DOWNLOAD)}."
        )

    def test_existe_rota_de_download(self):
        rotas = [rota.path for rota in app.routes if "download" in rota.path]
        assert rotas, (
            "Nenhuma rota de download publicada. O proxy atual "
            "(`/drive/imagem/{file_id}`) devolve a imagem para exibir, com cache de "
            "24h, e nao serve documento nem video."
        )

    def test_galeria_continua_publicando_o_id_do_arquivo(self):
        """
        Verde hoje e precisa continuar: qualquer rota de download vai precisar
        do id do arquivo no Drive, e e esse campo que o front repassa.
        `RespostaDrive` nao esta no CONTRATO de test_contrato_respostas.py.
        """
        assert "id" in RespostaDrive.model_fields
        assert "id" in RespostaItemGaleria.model_fields


class TestCargoUnico:
    """
    US10 / RF58: dois lideres nao podem ocupar o mesmo cargo ao mesmo tempo —
    mas o cargo e o par (nome, abrangencia). "Diretor regional do Sul" e
    "diretor regional do Centro-Oeste" sao cargos diferentes, e a cliente foi
    explicita nisso. Nao existe validacao nenhuma hoje.
    """

    def test_mesmo_cargo_em_regioes_diferentes_e_permitido(self, servico_lider):
        """
        Verde hoje, e o teste que trava a implementacao ingenua: unicidade so
        pelo nome do cargo recusaria o segundo cadastro e quebraria aqui.
        """
        servico_lider.criar_lider(
            SolicitacaoLider(nome="Ana Souza", cargo="Diretor Regional", regiao="Sul")
        )
        servico_lider.criar_lider(
            SolicitacaoLider(
                nome="Bruno Lima", cargo="Diretor Regional", regiao="Centro-Oeste"
            )
        )

        assert len(servico_lider.listar_lideres_atuais()) == 2

    def test_cargo_liberado_quando_o_antecessor_vira_anterior(self, servico_lider):
        """
        Verde hoje. Fim de mandato e marcacao manual (`is_antigo`), e o cargo
        tem de aceitar o sucessor — senao nenhuma troca de diretoria passa.
        """
        servico_lider.criar_lider(
            SolicitacaoLider(
                nome="Carlos Pereira", cargo="Diretor Nacional", is_antigo=True
            )
        )
        servico_lider.criar_lider(
            SolicitacaoLider(nome="Daniela Rocha", cargo="Diretor Nacional")
        )

        assert len(servico_lider.listar_lideres_atuais()) == 1
        assert len(servico_lider.listar_diretores_anteriores()) == 1

    def test_dois_vice_diretores_nacionais_ativos_sao_recusados(self, servico_lider):
        servico_lider.criar_lider(
            SolicitacaoLider(nome="Ana Souza", cargo="Vice-Diretor Nacional")
        )

        with pytest.raises(RECUSAS_ACEITAS):
            servico_lider.criar_lider(
                SolicitacaoLider(nome="Bruno Lima", cargo="Vice-Diretor Nacional")
            )

    def test_dois_diretores_na_mesma_regiao_sao_recusados(self, servico_lider):
        servico_lider.criar_lider(
            SolicitacaoLider(nome="Ana Souza", cargo="Diretor Regional", regiao="Sul")
        )

        with pytest.raises(RECUSAS_ACEITAS):
            servico_lider.criar_lider(
                SolicitacaoLider(nome="Bruno Lima", cargo="Diretor Regional", regiao="Sul")
            )

    def test_atualizacao_tambem_respeita_o_cargo_ocupado(self, servico_lider):
        """
        O caminho que costuma escapar: a regra entra no cadastro e nao na
        edicao, e o cargo duplicado volta por um PUT.
        """
        servico_lider.criar_lider(
            SolicitacaoLider(nome="Ana Souza", cargo="Vice-Diretor Nacional")
        )
        outro = servico_lider.criar_lider(
            SolicitacaoLider(nome="Bruno Lima", cargo="Tesoureiro Nacional")
        )

        with pytest.raises(RECUSAS_ACEITAS):
            servico_lider.atualizar_lider(
                outro.lider_id,
                SolicitacaoLider(nome="Bruno Lima", cargo="Vice-Diretor Nacional"),
            )


class TestCalendarioComEventosPassados:
    """
    US23 / RF59: o calendario precisa guardar registro dos eventos que ja
    ocorreram.

    Achado ao escrever esta especificacao: o recorte nao esta so no front. O
    back-end monta a consulta ao Google Calendar com `timeMin=agora`, ou seja,
    o evento passado nem chega a sair da API — e `maxResults=10` corta o resto.
    Quem for implementar a US23 mexendo apenas no filtro do
    `CalendarioSection.jsx` vai ver a lista continuar sem o passado.
    """

    @pytest.mark.xfail(strict=True, reason=PENDENTE)
    def test_consulta_nao_recorta_pelo_instante_atual(self, servico_calendario):
        url = servico_calendario._montar_url_evento()
        assert "timeMin" not in url, (
            "A consulta ao Google Calendar comeca em `agora`, entao evento passado "
            "nunca volta. Para guardar historico, remova o timeMin ou use uma data "
            "de corte do projeto."
        )

    @pytest.mark.xfail(strict=True, reason=PENDENTE)
    def test_consulta_pede_mais_que_dez_eventos(self, servico_calendario):
        url = servico_calendario._montar_url_evento()
        assert "maxResults=10&" not in url and not url.endswith("maxResults=10"), (
            "Com maxResults=10 o calendario trunca sem erro nenhum: some evento do "
            "fim da lista e ninguem percebe. Incluindo o passado, 10 nao cobre um ano."
        )

    def test_evento_passado_nao_e_descartado_na_conversao(self, servico_calendario):
        """
        Verde hoje: o descarte e no filtro da consulta, nao na conversao. Vale
        registrar para ninguem "resolver" a US23 filtrando data aqui.
        """
        registro = {
            "summary": "Acampamento Nacional 2024",
            "start": {"date": "2024-07-15"},
            "end": {"date": "2024-07-20"},
            "location": "Brasilia",
        }

        evento = servico_calendario._converter_evento(registro)

        assert evento is not None
        assert evento.data_inicio == date(2024, 7, 15)
        assert evento.nome == "Acampamento Nacional 2024"
