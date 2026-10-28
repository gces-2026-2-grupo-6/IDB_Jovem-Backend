from src.evento.schema import SituacaoEvento, SolicitacaoEvento, SolicitacaoSituacaoEvento
from src.shared.utils import validar_datas, validar_coordenadas
from src.evento.model import Evento
from src.evento.repository import RepositorioEvento
from src.calendario.service import ServicoCalendario
from src.mapa.service import ServicoMapa


def _limpar_nova_data_fora_do_adiado(evento: Evento) -> None:
    """US14: quem está ativo ou cancelado não carrega a data do adiamento."""
    if evento.situacao != SituacaoEvento.ADIADO:
        evento.nova_data = None


def _is_online(modalidade) -> bool:
    valor = getattr(modalidade, "value", modalidade)
    return str(valor).strip().lower() == "online"


class ServicoEvento:

    def __init__(
        self, repositorio: RepositorioEvento,
        google_calendario: ServicoCalendario,
        mapa_servico: ServicoMapa
    ):
        self.repositorio = repositorio
        self.calendario = google_calendario
        self.mapa_servico = mapa_servico

    def criar_evento(self, dados: SolicitacaoEvento):
        validar_datas(dados.data_inicio, dados.data_fim)
        evento = Evento(**dados.model_dump())
        _limpar_nova_data_fora_do_adiado(evento)
        evento = self.repositorio.salvar(evento)

        if _is_online(evento.modalidade):
            evento.modalidade = "online"
            evento.local_latitude = None
            evento.local_longitude = None
            evento.nome_local = None
            local_calendario = evento.link_transmissao or "Online"
        else:
            evento.modalidade = "presencial"
            evento.link_transmissao = None
            validar_coordenadas(evento.local_latitude, evento.local_longitude)
            nome_local = self.mapa_servico.buscar_endereco_por_coordenadas(
                evento.local_latitude,
                evento.local_longitude
            )
            evento.nome_local = nome_local
            local_calendario = nome_local

        evento = self.repositorio.salvar(evento)

        try:
            calendario_id = self.calendario.criar_evento(evento, local_calendario)
            evento.calendario_evento_id = calendario_id
            evento = self.repositorio.salvar(evento)

        except Exception as erro:
            print(f"Erro ao integrar com o Google Calendário: {erro}")
            raise

        return evento

    def listar_evento(self):
        return self.repositorio.buscar_todos()

    def buscar_evento(self, evento_id: int):
        evento = self.repositorio.buscar_por_id(evento_id)

        if not evento:
            raise ValueError("Evento não encontrado.")

        return evento

    def atualizar_evento(self, evento_id: int, mudancas: SolicitacaoEvento):
        evento = self.buscar_evento(evento_id)

        dados_mudanca = mudancas.model_dump(exclude_unset=True)

        for campo, novo_valor in dados_mudanca.items():
            setattr(evento, campo, novo_valor)

        _limpar_nova_data_fora_do_adiado(evento)
        validar_datas(evento.data_inicio, evento.data_fim)

        if _is_online(evento.modalidade):
            evento.modalidade = "online"
            evento.local_latitude = None
            evento.local_longitude = None
            evento.nome_local = None
            local_calendario = evento.link_transmissao or "Online"
        else:
            evento.modalidade = "presencial"
            evento.link_transmissao = None
            validar_coordenadas(evento.local_latitude, evento.local_longitude)
            evento.nome_local = self.mapa_servico.buscar_endereco_por_coordenadas(
                evento.local_latitude,
                evento.local_longitude
            )
            local_calendario = evento.nome_local

        if evento.calendario_evento_id:
            self.calendario.atualizar_evento(
                evento.calendario_evento_id,
                evento,
                local_calendario
            )

        return self.repositorio.salvar(evento)

    def alterar_situacao(self, evento_id: int, dados: SolicitacaoSituacaoEvento):
        """
        US14: marca o evento como cancelado ou adiado, ou desfaz a marcação.
        Nada é apagado e ninguém é avisado: a comunicação com os inscritos
        continua sendo feita pela equipe.
        """
        evento = self.buscar_evento(evento_id)
        evento.situacao = dados.situacao.value
        evento.nova_data = dados.nova_data
        evento = self.repositorio.salvar(evento)

        # A agenda do Google é um espelho: se falhar, o site já está certo e
        # a próxima edição do evento sincroniza de novo.
        if evento.calendario_evento_id:
            try:
                local_calendario = (
                    evento.link_transmissao or "Online"
                    if _is_online(evento.modalidade)
                    else evento.nome_local
                )
                self.calendario.atualizar_evento(
                    evento.calendario_evento_id, evento, local_calendario
                )
            except RuntimeError as erro:
                print(f"Erro ao atualizar a situacao no Google Calendario: {erro}")

        return evento

    def deletar_evento(self, evento_id: int):
        evento = self.buscar_evento(evento_id)

        if evento.calendario_evento_id:
            self.calendario.deletar_evento(evento.calendario_evento_id)

        self.repositorio.deletar(evento)

    def pesquisar_eventos(self, termo: str):
        termo = termo.strip()

        if len(termo) < 2:
            return []

        return self.repositorio.pesquisar_por_nome(termo)

    def listar_participantes(self, evento_id: int):
        self.buscar_evento(evento_id)
        return self.repositorio.buscar_participantes(evento_id)

    def adicionar_participante(self, evento_id: int, participante_id: int):
        self.buscar_evento(evento_id)

        participante = self.repositorio.buscar_participante_por_id(participante_id)
        if not participante:
            raise ValueError("Banda ou palestrante não encontrado.")

        if self.repositorio.buscar_vinculo(evento_id, participante_id):
            raise ValueError("Participante já vinculado a este evento.")

        self.repositorio.vincular_participante(evento_id, participante_id)
        return participante

    def remover_participante(self, evento_id: int, participante_id: int):
        vinculo = self.repositorio.buscar_vinculo(evento_id, participante_id)
        if not vinculo:
            raise ValueError("Vínculo entre evento e participante não encontrado.")

        self.repositorio.desvincular_participante(vinculo)
    