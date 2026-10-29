from datetime import datetime, date
from enum import Enum
from pydantic import BaseModel, field_validator, model_validator

from src.drive.utils import converter_link_para_proxy, montar_url_download


class TipoEvento(str, Enum):
    CONFERENCIA = "Conferência"
    ACAMPAMENTO = "Acampamento"
    CAMPANHA_NACIONAL = "Campanha Nacional"
    OUTROS = "Outros"


class SituacaoEvento(str, Enum):
    """US14: o evento cancelado ou adiado continua no site, com aviso."""
    ATIVO = "ativo"
    CANCELADO = "cancelado"
    ADIADO = "adiado"


class ModalidadeEvento(str, Enum):
    PRESENCIAL = "presencial"
    ONLINE = "online"


class BaseEvento(BaseModel):
    nome: str
    tipo_evento: TipoEvento | None = None
    descricao: str | None = None
    # As colunas aceitam nulo no banco. Exigir os dois numeros aqui fazia um
    # unico evento sem coordenadas derrubar a listagem inteira com erro 500,
    # porque a falha e na serializacao da resposta e vale para todos os itens.
    # A criacao exige coordenadas apenas quando presencial (US19).
    local_latitude: float | None = None
    local_longitude: float | None = None
    data_inicio: datetime
    data_fim: datetime
    link_galeria: str | None = None
    formulario_link: str | None = None
    formulario_participante_link: str | None = None
    link_imagem: str | None = None
    datas: list[date] | None = None
    situacao: SituacaoEvento = SituacaoEvento.ATIVO
    # Só faz sentido no adiado; o serviço zera nas outras situações.
    nova_data: datetime | None = None

    modalidade: ModalidadeEvento = ModalidadeEvento.PRESENCIAL
    link_transmissao: str | None = None

    @field_validator("modalidade", mode="before")
    @classmethod
    def _normalizar_modalidade(cls, v):
        if v is None:
            return ModalidadeEvento.PRESENCIAL
        if isinstance(v, bool):
            return ModalidadeEvento.ONLINE if v else ModalidadeEvento.PRESENCIAL
        if isinstance(v, str):
            v_lower = v.strip().lower()
            if v_lower in ("online", "true"):
                return ModalidadeEvento.ONLINE
            if v_lower in ("presencial", "false"):
                return ModalidadeEvento.PRESENCIAL
        return v

class SolicitacaoEvento(BaseEvento):
    """"
    Modelo para a solicitação de criação ou atualização de um evento.
    Herda os campos básicos de Baseevento.
    """
    tipo_evento: TipoEvento
    local_latitude: float | None = None
    local_longitude: float | None = None

    @model_validator(mode="after")
    def _validar_local_por_modalidade(self):
        if self.modalidade == ModalidadeEvento.PRESENCIAL:
            if self.local_latitude is None or self.local_longitude is None:
                raise ValueError("Evento presencial exige latitude e longitude.")
            self.link_transmissao = None
        else:
            self.local_latitude = None
            self.local_longitude = None
        return self

class SolicitacaoSituacaoEvento(BaseModel):
    """
    Corpo do PATCH /evento/{id}/situacao (US14). Marcar como "ativo" desfaz
    a marcação; nova_data só vale para "adiado".
    """
    situacao: SituacaoEvento
    nova_data: datetime | None = None

    @model_validator(mode="after")
    def _nova_data_so_no_adiado(self):
        if self.situacao != SituacaoEvento.ADIADO:
            self.nova_data = None
        return self


class RespostaResumoExclusaoEvento(BaseModel):
    evento_id: int
    participantes: int
    voluntarios: int
    atividades: int
    convidados: int


class RespostaEvento(BaseEvento):
    evento_id: int
    calendario_evento_id: str | None = None
    nome_local: str | None = None

    class Config:
        from_attributes = True

    @field_validator("link_imagem")
    @classmethod
    def _link_imagem_para_proxy(cls, valor: str | None) -> str | None:
        return converter_link_para_proxy(valor)


class RespostaItemGaleria(BaseModel):
    id: str
    image: str
    event: str
    location: str
    # US11: link do botão "Baixar". Preenchido a partir do id quando não vier.
    url_download: str = ""

    @model_validator(mode="after")
    def _preencher_download(self):
        if not self.url_download:
            self.url_download = montar_url_download(self.id)
        return self
