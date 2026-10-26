from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Depends, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.database import obter_banco
from src.drive.service import ServicoDrive
from src.drive.schema import RespostaDrive
from src.material.repository import RepositorioMaterial
from src.material.service import ServicoMaterial
from src.security import verificar_roles

router = APIRouter(prefix="/galeria", tags=["Galeria do Google Drive"])

router_imagem = APIRouter(prefix="/drive", tags=["Imagens do Google Drive"])


@router_imagem.get("/imagem/{file_id}")
def proxy_imagem(file_id: str, banco: Session = Depends(obter_banco)):
    """
    Proxy publico de imagens do Google Drive com cache no banco. No primeiro
    acesso baixa o arquivo do Drive e guarda em base64; nas requisicoes
    seguintes serve direto do banco, sem voltar ao Drive. Devolve os bytes com
    o Content-Type correto e cache de 24h no cliente.
    """
    servico = ServicoDrive()

    try:
        content_type, conteudo = servico.obter_imagem_com_cache(banco, file_id)

    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro

    except RuntimeError as erro:
        raise HTTPException(status_code=502, detail=str(erro)) from erro

    return Response(
        content=conteudo,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )

@router_imagem.get(
    "/download/{file_id}",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"application/octet-stream": {}},
            "description": "O arquivo, com o nome original no Content-Disposition.",
        },
        404: {"description": "Arquivo inexistente ou que não pode ser baixado."},
        502: {"description": "Falha ao falar com o Google Drive."},
    },
)
def baixar_arquivo(file_id: str, banco: Session = Depends(obter_banco)):
    """
    Download público de fotos, vídeos e documentos do Drive (US11), sem login.

    A rota usa a conta institucional do Drive, então não pode virar uma porta
    para qualquer arquivo dela. Só sai daqui: imagem (as fotos da galeria, que
    o proxy de imagem já publica) ou arquivo cadastrado como material pela
    superadministradora. O resto responde 404, sem dizer se o arquivo existe.
    """
    servico = ServicoDrive()

    try:
        metadados = servico.obter_metadados(file_id)

        liberado = metadados["content_type"].startswith("image/") or ServicoMaterial(
            RepositorioMaterial(banco)
        ).arquivo_cadastrado(file_id)
        if not liberado:
            raise ValueError("Arquivo não encontrado.")

        nome, content_type, blocos = servico.transmitir_arquivo(file_id, metadados)

    except ValueError as erro:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.") from erro

    except RuntimeError as erro:
        raise HTTPException(status_code=502, detail=str(erro)) from erro

    return StreamingResponse(
        blocos,
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(nome)}"},
    )


@router.get("/fotos", response_model=list[RespostaDrive])
def listar_fotos(
    pasta: str = Query(..., min_length=1),
    usuario_logado: dict = Depends(verificar_roles(["admin", "superadmin"])),
):
    """
    Lista as fotos armazenadas no Google Drive por nome de pasta.
    Autenticação com o Google feita de forma automatizada pelo servidor.
    """
    servico = ServicoDrive()

    try:
        return servico.listar_fotos(pasta)

    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro

    except RuntimeError as erro:
        raise HTTPException(status_code=502, detail=str(erro)) from erro
