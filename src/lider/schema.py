from pydantic import BaseModel, ConfigDict, field_validator


class BaseLider(BaseModel):
    nome: str
    cargo: str
    imagem_url: str | None = None
    # Marcação manual (US05): nada no sistema move um líder para "anterior".
    is_antigo: bool = False
    ordem: int = 0
    regiao: str | None = None
    mini_biografia: str | None = None
    # Objeto JSON no formato {"rede": "link"}, ex.: {"instagram": "https://..."}.
    redes_sociais: dict[str, str] | None = None

    @field_validator("regiao", "mini_biografia", mode="before")
    @classmethod
    def _texto_vazio_para_nulo(cls, valor):
        if isinstance(valor, str):
            return valor.strip() or None
        return valor

    @field_validator("redes_sociais", mode="before")
    @classmethod
    def _normalizar_redes_sociais(cls, valor):
        # O painel atual envia "" quando o campo fica em branco; tratar como
        # ausência evita recusar o salvamento de um líder sem redes.
        if valor is None or valor == "":
            return None

        if not isinstance(valor, dict):
            raise ValueError(
                'redes_sociais deve ser um objeto JSON, '
                'ex.: {"instagram": "https://instagram.com/perfil"}'
            )

        redes = {}
        for rede, link in valor.items():
            if not isinstance(rede, str) or not rede.strip():
                raise ValueError("O nome de cada rede social deve ser um texto não vazio.")
            if link is None:
                continue
            if not isinstance(link, str):
                raise ValueError(f"O link da rede '{rede}' deve ser um texto.")
            if link.strip():
                redes[rede.strip()] = link.strip()

        return redes or None


class SolicitacaoLider(BaseLider):
    pass


class RespostaLider(BaseLider):
    lider_id: int

    model_config = ConfigDict(from_attributes=True)
