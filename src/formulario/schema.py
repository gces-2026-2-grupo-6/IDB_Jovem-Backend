from pydantic import BaseModel


class RespostaInscricaoFormulario(BaseModel):
    evento_id: int
    voluntario_id: int
    nome: str
    email: str
    status: str
    resposta_id: str
    link_resposta: str

    class Config:
        from_attributes = True


class RespostaInscricaoParticipante(BaseModel):
    """Inscrito no formulario de participantes (US09).

    Sem campo de status: a aprovacao existe apenas no fluxo de voluntariado.
    """

    evento_id: int
    participante_id: int
    nome: str
    email: str
    resposta_id: str
    link_resposta: str

    class Config:
        from_attributes = True
