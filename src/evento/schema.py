from datetime import datetime, date
from enum import Enum
from pydantic import BaseModel, field_validator

from src.drive.utils import converter_link_para_proxy


class TipoEvento(str, Enum):
    CONFERENCIA = "Conferência"
    ACAMPAMENTO = "Acampamento"
    CAMPANHA_NACIONAL = "Campanha Nacional"
    OUTROS = "Outros"


class BaseEvento(BaseModel):
    nome: str
    tipo_evento: TipoEvento | None = None
    descricao: str | None = None
    local_latitude: float
    local_longitude: float
    data_inicio: datetime
    data_fim: datetime
    link_galeria: str | None = None
    formulario_link: str | None = None
    link_imagem: str | None = None
    datas: list[date] | None = None

class SolicitacaoEvento(BaseEvento):
    """"
    Modelo para a solicitação de criação ou atualização de um evento.
    Herda os campos básicos de Baseevento.
    """
    tipo_evento: TipoEvento

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
