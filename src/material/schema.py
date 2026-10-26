from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from src.drive.utils import link_de_download


class TipoMaterial(str, Enum):
    FOTO = "foto"
    VIDEO = "video"
    DOCUMENTO = "documento"


class SolicitacaoMaterial(BaseModel):
    titulo: str
    descricao: str | None = None
    tipo: TipoMaterial
    # Link do arquivo no Drive (ou link externo, como um vídeo no YouTube).
    link: str

    @field_validator("titulo")
    @classmethod
    def _titulo_obrigatorio(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("O título é obrigatório.")
        return valor

    @field_validator("descricao", mode="before")
    @classmethod
    def _descricao_vazia_para_nulo(cls, valor):
        if isinstance(valor, str):
            return valor.strip() or None
        return valor

    @field_validator("link")
    @classmethod
    def _link_http(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor.startswith(("https://", "http://")):
            raise ValueError("O link deve começar com https:// ou http://.")
        return valor


class RespostaMaterial(BaseModel):
    material_id: int
    titulo: str
    descricao: str | None = None
    tipo: TipoMaterial
    link: str
    # Link do botão "Baixar": arquivo do Drive passa pela rota de download do
    # backend; link externo vem como está.
    url_download: str = ""
    criado_em: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _preencher_download(self):
        if not self.url_download:
            self.url_download = link_de_download(self.link)
        return self
