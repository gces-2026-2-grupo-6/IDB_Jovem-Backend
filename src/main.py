from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from starlette.middleware.sessions import SessionMiddleware
from src.config import configuracoes
from src.admin.controller import router as admin_router
from src.banda_palestrante.controller import router as banda_palestrante_router
from src.formulario.controller import router as formulario_router
from src.produto.controller import router as produto_router
from src.voluntario.controller import router as voluntario_router
from src.auth.controller import router as auth_routers
from src.evento.controller import router as evento_routers
from src.atividade.controller import router as atividade_routers
from src.drive.controller import router as drive_routers
from src.drive.controller import router_imagem as drive_imagem_router
from src.mapa.controller import router as mapa_routers
from src.lider.controller import router as lider_routers
from src.painel.controller import router as painel_router
from src.material.controller import router as material_router

app = FastAPI(title="IDB Jovem Backend")

origens_permitidas = [
    origem.strip()
    for origem in configuracoes.CORS_ORIGINS.split(",")
    if origem.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origens_permitidas,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key=configuracoes.SECRET_KEY)

app.include_router(admin_router)
app.include_router(banda_palestrante_router)
app.include_router(formulario_router)
app.include_router(produto_router)
app.include_router(voluntario_router)
app.include_router(auth_routers)
app.include_router(evento_routers)
app.include_router(atividade_routers)
app.include_router(drive_routers)
app.include_router(drive_imagem_router)
app.include_router(mapa_routers)
app.include_router(lider_routers)
app.include_router(painel_router)
app.include_router(material_router)

@app.get("/")
def read_root():
    return {"message": "IDB Jovem Backend está rodando!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
