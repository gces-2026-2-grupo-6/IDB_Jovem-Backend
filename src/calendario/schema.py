from datetime import date, datetime

from pydantic import BaseModel

class RespostaEvento(BaseModel):
    nome: str
    data_inicio: date
    data_fim: date | None = None
    local: str

    class Config:
        from_attributes = True

class SolicitacaoEvento(BaseModel):
    nome: str
    local: str
    descricao: str | None = None
    data_inicio: datetime
    data_fim: datetime
