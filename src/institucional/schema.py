from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class RespostaInstitucional(BaseModel):
    """
    Missão, visão e valores exibidos na página "Quem somos" (US22).

    `valores` sempre vem como lista — vazia enquanto nada foi salvo. Missão e
    visão nulas significam "ainda não configurado"; o front só mostra o que
    existir.
    """

    model_config = ConfigDict(from_attributes=True)

    missao: str | None = None
    visao: str | None = None
    valores: list[str]


class SolicitacaoInstitucional(BaseModel):
    """
    Substitui o conteúdo institucional por inteiro. Texto em branco vira nulo
    e valores em branco são descartados; enviar tudo vazio é recusado para não
    apagar a página por acidente.
    """

    missao: str | None = None
    visao: str | None = None
    valores: list[str] = []

    @field_validator("missao", "visao", mode="before")
    @classmethod
    def _limpar_texto(cls, valor):
        if valor is None:
            return None
        if not isinstance(valor, str):
            raise ValueError("A missão e a visão devem ser textos.")
        valor = valor.strip()
        return valor or None

    @field_validator("valores", mode="before")
    @classmethod
    def _limpar_valores(cls, valores):
        if valores is None:
            return []
        if not isinstance(valores, (list, tuple)):
            raise ValueError("Os valores devem ser uma lista de textos.")
        limpos = []
        for valor in valores:
            if not isinstance(valor, str):
                raise ValueError("Cada valor deve ser um texto.")
            valor = valor.strip()
            if valor:
                limpos.append(valor)
        return limpos

    @model_validator(mode="after")
    def _exigir_algum_conteudo(self):
        if not self.missao and not self.visao and not self.valores:
            raise ValueError("Preencha ao menos a missão, a visão ou um valor.")
        return self
