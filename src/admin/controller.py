from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import obter_banco
from src.admin.repository import RepositorioAdmin
from src.admin.service import ServicoAdmin
from src.admin.schema import SolicitacaoAdmin, RespostaAdmin
from src.security import verificar_roles


router = APIRouter(prefix="/admin", tags=["admin"])


def get_servico(db: Session = Depends(obter_banco)):
    repositorio = RepositorioAdmin(db)
    return ServicoAdmin(repositorio)

@router.post("/", response_model=RespostaAdmin, status_code=status.HTTP_201_CREATED)
def criar_admin(
    solicitacao: SolicitacaoAdmin,
    servico: ServicoAdmin = Depends(get_servico),
    _: dict = Depends(verificar_roles(["superadmin"]))
):
    try:
        return servico.criar_admin(solicitacao)

    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro

@router.get("/", response_model=list[RespostaAdmin])
def listar_admins(
    servico: ServicoAdmin = Depends(get_servico),
    _: dict = Depends(verificar_roles(["superadmin"]))
):
    return servico.listar_admins()


@router.get("/{admin_id}", response_model=RespostaAdmin)
def buscar_admin(
    admin_id: int,
    servico: ServicoAdmin = Depends(get_servico),
    _: dict = Depends(verificar_roles(["superadmin"]))
):
    try:
        return servico.buscar_admin(admin_id)

    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro

@router.delete("/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar_admin(
    admin_id: int,
    servico: ServicoAdmin = Depends(get_servico),
    usuario_logado: dict = Depends(verificar_roles(["superadmin"]))
):
    try:
        servico.deletar_admin(admin_id, usuario_logado)

    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
