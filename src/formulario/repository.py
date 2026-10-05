import os
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from src.evento.model import Evento
from src.formulario.schema import (
    RespostaInscricaoFormulario,
    RespostaInscricaoParticipante,
)
from src.auth.service import ServicoAuth
from src.participante.models import Inscricao, Participante
from src.voluntario.models import Trabalha, Voluntario

STATUS_PENDENTE = "pendente"

class RepositorioFormulario:
    def __init__(self):
        self.refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
        self.servico_auth = ServicoAuth()

    def _obter_token_valido(self) -> str:
        """Busca o refresh_token do .env, renova no Google e retorna o access_token ativo."""
        if not self.refresh_token:
            raise RuntimeError("GOOGLE_REFRESH_TOKEN nao configurado no arquivo .env")
        try:
            credenciais = self.servico_auth.obter_credenciais_validas(self.refresh_token)
            return credenciais.token
        except Exception as erro:
            raise RuntimeError("Falha automatica ao renovar credenciais do Google para o Forms") from erro

    def _extrair_formulario_id_link(self, link: str) -> str | None:
        if "/forms/d/" not in link:
            return None
        parte = link.split("/forms/d/")[-1]
        return parte.split("/")[0] if parte else None

    def _definir_formulario_id(self, link_formulario: str) -> str:
        formulario_id = self._extrair_formulario_id_link(link_formulario)
        if not formulario_id:
            raise ValueError("Use o link completo do Forms para extrair o formulario_id")
        return formulario_id

    def _montar_link_resposta(self, formulario_id: str, resposta_id: str) -> str:
        return (
            f"https://docs.google.com/forms/d/{formulario_id}/edit#response={resposta_id}"
        )

    def _montar_requisicao(self, url: str, token: str) -> Request:
        requisicao = Request(url)
        requisicao.add_header("Authorization", f"Bearer {token}")
        requisicao.add_header("Accept", "application/json")
        return requisicao

    def _buscar_json(self, url: str, token: str, erro_mensagem: str) -> dict:
        requisicao = self._montar_requisicao(url, token)
        try:
            with urlopen(requisicao, timeout=10) as resposta:
                corpo = resposta.read().decode("utf-8")
        except (HTTPError, URLError) as erro:
            raise RuntimeError(erro_mensagem) from erro
        return json.loads(corpo)

    def _buscar_formulario(self, token: str, formulario_id: str) -> dict:
        url = f"https://forms.googleapis.com/v1/forms/{formulario_id}"
        return self._buscar_json(url, token, "Falha ao buscar formulario no Google Forms")

    def _buscar_respostas(self, token: str, formulario_id: str) -> list[dict]:
        url = f"https://forms.googleapis.com/v1/forms/{formulario_id}/responses"
        dados = self._buscar_json(url, token, "Falha ao buscar respostas no Google Forms")
        return dados.get("responses", [])

    def _mapear_perguntas(self, formulario: dict) -> dict[str, str]:
        mapa: dict[str, str] = {}
        for item in formulario.get("items", []):
            pergunta = item.get("questionItem", {}).get("question", {})
            pergunta_id = pergunta.get("questionId")
            if pergunta_id:
                mapa[pergunta_id] = item.get("title", "")
        return mapa

    def _localizar_id_pergunta(self, mapa: dict[str, str], titulo: str) -> str | None:
        titulo_normalizado = titulo.strip().lower()
        for pergunta_id, nome in mapa.items():
            if nome.strip().lower() == titulo_normalizado:
                return pergunta_id
        return None

    def _extrair_texto_resposta(self, respostas: dict, pergunta_id: str | None) -> str | None:
        if not pergunta_id:
            return None
        resposta = respostas.get(pergunta_id, {})
        textos = resposta.get("textAnswers", {}).get("answers", [])
        if textos:
            return textos[0].get("value")
        return None

    def _buscar_evento(self, db: Session, evento_id: int) -> Evento:
        evento = db.query(Evento).filter(Evento.evento_id == evento_id).first()
        if not evento:
            raise ValueError("Evento nao encontrado")
        return evento

    def _salvar_voluntario(
        self,
        db: Session,
        nome: str,
        email: str,
    ) -> Voluntario:
        voluntario = db.query(Voluntario).filter(Voluntario.email == email).first()
        if voluntario:
            voluntario.nome = nome
            db.add(voluntario)
            return voluntario
        voluntario = Voluntario(
            nome=nome,
            email=email,
        )
        db.add(voluntario)
        db.flush()
        return voluntario

    def _garantir_trabalho(
        self,
        db: Session,
        voluntario_id: int,
        evento_id: int,
        resposta_id: str,
    ) -> Trabalha:
        trabalho = (
            db.query(Trabalha)
            .filter(
                Trabalha.voluntario_id == voluntario_id,
                Trabalha.evento_id == evento_id,
            )
            .first()
        )
        if trabalho:
            trabalho.resposta_id = resposta_id
            db.add(trabalho)
            return trabalho
        trabalho = Trabalha(
            voluntario_id=voluntario_id,
            evento_id=evento_id,
            status=STATUS_PENDENTE,
            resposta_id=resposta_id,
        )
        db.add(trabalho)
        return trabalho

    def _montar_inscricao(
        self,
        contexto: dict,
        resposta: dict,
    ) -> RespostaInscricaoFormulario | None:
        resposta_id = resposta.get("responseId", "")
        respostas_campos = resposta.get("answers", {})
        nome = self._extrair_texto_resposta(respostas_campos, contexto["id_nome"])
        email = self._extrair_texto_resposta(respostas_campos, contexto["id_email"])
        if not nome or not email or not resposta_id:
            return None
        voluntario = self._salvar_voluntario(contexto["db"], nome, email)
        trabalho = self._garantir_trabalho(
            contexto["db"],
            voluntario.voluntario_id,
            contexto["evento"].evento_id,
            resposta_id,
        )
        return RespostaInscricaoFormulario(
            evento_id=contexto["evento"].evento_id,
            voluntario_id=voluntario.voluntario_id,
            nome=voluntario.nome,
            email=voluntario.email,
            status=trabalho.status,
            resposta_id=resposta_id,
            link_resposta=self._montar_link_resposta(
                contexto["formulario_id"],
                resposta_id,
            ),
        )

    def _preparar_contexto(self, db: Session, evento: Evento, link_formulario: str) -> dict:
        """Le o formulario no Google e monta o contexto comum aos dois fluxos."""
        token = self._obter_token_valido()
        formulario_id = self._definir_formulario_id(link_formulario)

        formulario = self._buscar_formulario(token, formulario_id)
        respostas = self._buscar_respostas(token, formulario_id)
        mapa_perguntas = self._mapear_perguntas(formulario)

        return {
            "db": db,
            "evento": evento,
            "formulario_id": formulario_id,
            "id_nome": self._localizar_id_pergunta(mapa_perguntas, "Nome"),
            "id_email": self._localizar_id_pergunta(mapa_perguntas, "Email"),
            "respostas": respostas,
        }

    def _salvar_participante(self, db: Session, nome: str, email: str) -> Participante:
        participante = (
            db.query(Participante).filter(Participante.email == email).first()
        )
        if participante:
            participante.nome = nome
            db.add(participante)
            return participante
        participante = Participante(nome=nome, email=email)
        db.add(participante)
        db.flush()
        return participante

    def _garantir_inscricao(
        self,
        db: Session,
        participante_id: int,
        evento_id: int,
        resposta_id: str,
    ) -> Inscricao:
        inscricao = (
            db.query(Inscricao)
            .filter(
                Inscricao.participante_id == participante_id,
                Inscricao.evento_id == evento_id,
            )
            .first()
        )
        if inscricao:
            inscricao.resposta_id = resposta_id
            db.add(inscricao)
            return inscricao
        inscricao = Inscricao(
            participante_id=participante_id,
            evento_id=evento_id,
            resposta_id=resposta_id,
        )
        db.add(inscricao)
        return inscricao

    def _montar_participante(
        self,
        contexto: dict,
        resposta: dict,
    ) -> RespostaInscricaoParticipante | None:
        resposta_id = resposta.get("responseId", "")
        respostas_campos = resposta.get("answers", {})
        nome = self._extrair_texto_resposta(respostas_campos, contexto["id_nome"])
        email = self._extrair_texto_resposta(respostas_campos, contexto["id_email"])
        if not nome or not email or not resposta_id:
            return None
        participante = self._salvar_participante(contexto["db"], nome, email)
        self._garantir_inscricao(
            contexto["db"],
            participante.participante_id,
            contexto["evento"].evento_id,
            resposta_id,
        )
        return RespostaInscricaoParticipante(
            evento_id=contexto["evento"].evento_id,
            participante_id=participante.participante_id,
            nome=participante.nome,
            email=participante.email,
            resposta_id=resposta_id,
            link_resposta=self._montar_link_resposta(
                contexto["formulario_id"],
                resposta_id,
            ),
        )

    def listar_inscricoes(
        self,
        db: Session,
        evento_id: int,
    ) -> list[RespostaInscricaoFormulario]:
        """Inscritos no formulario de voluntariado do evento."""
        evento = self._buscar_evento(db, evento_id)
        if not evento.formulario_link:
            raise ValueError("Evento sem formulario configurado")

        contexto = self._preparar_contexto(db, evento, evento.formulario_link)

        lista: list[RespostaInscricaoFormulario] = []
        for resposta in contexto["respostas"]:
            inscricao = self._montar_inscricao(contexto, resposta)
            if inscricao:
                lista.append(inscricao)
        db.commit()
        return lista

    def listar_participantes(
        self,
        db: Session,
        evento_id: int,
    ) -> list[RespostaInscricaoParticipante]:
        """Inscritos no formulario de participantes do evento (US09)."""
        evento = self._buscar_evento(db, evento_id)
        if not evento.formulario_participante_link:
            raise ValueError("Evento sem formulario de participantes configurado")

        contexto = self._preparar_contexto(
            db, evento, evento.formulario_participante_link
        )

        lista: list[RespostaInscricaoParticipante] = []
        for resposta in contexto["respostas"]:
            participante = self._montar_participante(contexto, resposta)
            if participante:
                lista.append(participante)
        db.commit()
        return lista
