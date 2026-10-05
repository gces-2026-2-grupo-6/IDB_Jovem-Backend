from sqlalchemy import Column, Integer, Text, ForeignKey
from src.database import Base


class Participante(Base):
    """
    Pessoa inscrita para assistir a um evento (US09).

    Nao confundir com a tabela `participa` (src/banda_palestrante/model.py),
    que liga bandas e palestrantes ao evento. Aqui o participante e quem se
    inscreve pelo formulario publico, em fluxo separado do voluntariado.
    """

    __tablename__ = "participante"

    participante_id = Column(Integer, primary_key=True, autoincrement=True)
    nome            = Column(Text, nullable=False)
    email           = Column(Text, unique=True, nullable=False)


class Inscricao(Base):
    """
    Vinculo entre participante e evento, espelho de `trabalha` para o fluxo
    de voluntariado. Sem coluna de status: a aprovacao pendente/aprovado/
    reprovado existe apenas no voluntariado (criterio 3 da US09).
    """

    __tablename__ = "inscricao"

    participante_id = Column(
        Integer,
        ForeignKey("participante.participante_id", ondelete="CASCADE"),
        primary_key=True,
    )
    evento_id = Column(
        Integer,
        ForeignKey("evento.evento_id", ondelete="CASCADE"),
        primary_key=True,
    )
    resposta_id = Column(Text, nullable=True)
