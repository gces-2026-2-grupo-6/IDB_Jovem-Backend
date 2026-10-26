from pydantic import BaseModel, field_validator


class RespostaLinksPainel(BaseModel):
    """
    Links fixados na página inicial do painel da superadministradora (US10).
    Campo nulo = link ainda não configurado; o front esconde o card.
    """
    link_cadastro_lideres: str | None = None
    link_planilha_lideres: str | None = None


class SolicitacaoLinksPainel(BaseModel):
    """
    Atualização parcial: só os campos enviados mudam. Enviar "" ou null
    remove o link fixado.
    """
    link_cadastro_lideres: str | None = None
    link_planilha_lideres: str | None = None

    @field_validator("link_cadastro_lideres", "link_planilha_lideres", mode="before")
    @classmethod
    def _validar_link(cls, valor):
        if valor is None:
            return None
        if not isinstance(valor, str):
            raise ValueError("O link deve ser um texto.")
        valor = valor.strip()
        if not valor:
            return None
        if not valor.startswith(("https://", "http://")):
            raise ValueError("O link deve começar com https:// ou http://.")
        return valor
