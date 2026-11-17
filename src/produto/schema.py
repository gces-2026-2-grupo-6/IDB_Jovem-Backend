from pydantic import BaseModel, field_validator

from src.drive.utils import converter_link_para_proxy


class BaseProduto(BaseModel):
    nome: str
    descricao: str | None = None
    link_produto: str | None = None
    link_imagem: str | None = None
    # US21: formulario do Google onde o visitante registra o pedido/interesse.
    formulario_pedido_link: str | None = None


class SolicitacaoProduto(BaseProduto):
    pass


class RespostaProduto(BaseProduto):
    produto_id: int

    class Config:
        from_attributes = True

    @field_validator("link_imagem")
    @classmethod
    def _link_imagem_para_proxy(cls, valor: str | None) -> str | None:
        return converter_link_para_proxy(valor)
