from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from src.drive.utils import link_de_download, link_de_preview

class TipoMaterial(str, Enum):
    FOTO = "foto"
    VIDEO = "video"
    DOCUMENTO = "documento"

class SolicitacaoMaterial(BaseModel):
    titulo: str
    descricao: str | None = None
    tipo: TipoMaterial
    link: str
    link_preview: str | None = None

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

    @field_validator("link_preview", mode="before")
    @classmethod
    def _link_preview_opcional(cls, valor):
        if valor is None:
            return None
        if not isinstance(valor, str):
            return valor
        valor = valor.strip()
        if not valor:
            return None
        return cls._link_http(valor)

class RespostaMaterial(BaseModel):
    material_id: int
    titulo: str
    descricao: str | None = None
    tipo: TipoMaterial
    link: str
    link_preview: str | None = None
    url_download: str = ""
    url_preview: str | None = None
    criado_em: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _preencher_links(self):
        if not self.url_download:
            self.url_download = link_de_download(self.link)
        if not self.url_preview:
            self.url_preview = link_de_preview(self.link, self.tipo.value, self.link_preview)
        return self
