from pydantic import BaseModel, model_validator

from src.drive.utils import montar_url_download


class RespostaDrive(BaseModel):
    id: str
    nome: str
    url_visualizacao: str
    # US11: link do botão "Baixar". Preenchido a partir do id quando não vier.
    url_download: str = ""

    class Config:
        from_attributes = True

    @model_validator(mode="after")
    def _preencher_download(self):
        if not self.url_download:
            self.url_download = montar_url_download(self.id)
        return self
