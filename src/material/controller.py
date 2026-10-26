from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.database import obter_banco
from src.lider.schema import ErroResposta
from src.material.repository import RepositorioMaterial
from src.material.schema import RespostaMaterial, SolicitacaoMaterial, TipoMaterial
from src.material.service import ServicoMaterial
from src.security import verificar_roles

router = APIRouter(prefix="/material", tags=["material"])

RESPOSTAS_AUTORIZACAO = {
    401: {"model": ErroResposta, "description": "Token de acesso expirado ou inválido."},
    403: {"model": ErroResposta, "description": "Token ausente ou sem o papel superadmin."},
}
RESPOSTA_NAO_ENCONTRADO = {
    404: {"model": ErroResposta, "description": "Material não encontrado."},
}


def get_servico(db: Session = Depends(obter_banco)):
    return ServicoMaterial(RepositorioMaterial(db))


# Leitura aberta: "todas as pessoas podem baixar, sem login" (cliente, 06/10).
@router.get("/", response_model=list[RespostaMaterial])
def listar_materiais(
    tipo: TipoMaterial | None = Query(None, description="Filtra por foto, video ou documento."),
    servico: ServicoMaterial = Depends(get_servico),
):
    return servico.listar_materiais(tipo)


@router.get("/{material_id}", response_model=RespostaMaterial, responses=RESPOSTA_NAO_ENCONTRADO)
def buscar_material(material_id: int, servico: ServicoMaterial = Depends(get_servico)):
    try:
        return servico.buscar_material(material_id)
    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro


# Escrita: "só o superadmin envia" (cliente, 06/10).
@router.post(
    "/",
    response_model=RespostaMaterial,
    status_code=status.HTTP_201_CREATED,
    responses=RESPOSTAS_AUTORIZACAO,
)
def criar_material(
    solicitacao: SolicitacaoMaterial,
    servico: ServicoMaterial = Depends(get_servico),
    _: dict = Depends(verificar_roles(["superadmin"])),
):
    return servico.criar_material(solicitacao)


@router.put(
    "/{material_id}",
    response_model=RespostaMaterial,
    responses={**RESPOSTAS_AUTORIZACAO, **RESPOSTA_NAO_ENCONTRADO},
)
def atualizar_material(
    material_id: int,
    solicitacao: SolicitacaoMaterial,
    servico: ServicoMaterial = Depends(get_servico),
    _: dict = Depends(verificar_roles(["superadmin"])),
):
    try:
        return servico.atualizar_material(material_id, solicitacao)
    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro


@router.delete(
    "/{material_id}",
    status_code=204,
    responses={**RESPOSTAS_AUTORIZACAO, **RESPOSTA_NAO_ENCONTRADO},
)
def deletar_material(
    material_id: int,
    servico: ServicoMaterial = Depends(get_servico),
    _: dict = Depends(verificar_roles(["superadmin"])),
):
    try:
        servico.deletar_material(material_id)
    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro
