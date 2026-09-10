import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from src.admin.controller import router as admin_router, get_servico as get_servico_admin
from src.banda_palestrante.controller import router as banda_router, get_servico as get_servico_banda
from src.atividade.controller import router as atividade_router, get_servico as get_servico_atividade
from src.evento.controller import router as evento_router, get_servico as get_servico_evento
from src.voluntario.controller import router as voluntario_router, get_servico as get_servico_voluntario
from src.produto.controller import router as produto_router, get_servico as get_servico_produto
from src.security import obter_usuario_atual
from src.evento.schema import RespostaEvento
from src.voluntario.schema import RespostaVoluntario
from src.produto.schema import RespostaProduto



USUARIO_ADMIN = {"sub": "user-123", "realm_access": {"roles": ["admin", "superadmin"]}}
USUARIO_SUPERADMIN = {"sub": "uuid-superadmin", "realm_access": {"roles": ["superadmin"]}}




@pytest.fixture
def client_admin():
    mock = MagicMock()
    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_servico_admin] = lambda: mock
    app.dependency_overrides[obter_usuario_atual] = lambda: USUARIO_SUPERADMIN
    with TestClient(app) as c:
        yield c, mock
    app.dependency_overrides.clear()


@pytest.fixture
def client_banda():
    mock = MagicMock()
    app = FastAPI()
    app.include_router(banda_router)
    app.dependency_overrides[get_servico_banda] = lambda: mock
    app.dependency_overrides[obter_usuario_atual] = lambda: USUARIO_ADMIN
    with TestClient(app) as c:
        yield c, mock
    app.dependency_overrides.clear()


@pytest.fixture
def client_atividade():
    mock = MagicMock()
    app = FastAPI()
    app.include_router(atividade_router)
    app.dependency_overrides[get_servico_atividade] = lambda: mock
    with TestClient(app) as c:
        yield c, mock
    app.dependency_overrides.clear()


@pytest.fixture
def client_evento():
    mock = MagicMock()
    app = FastAPI()
    app.include_router(evento_router)
    app.dependency_overrides[get_servico_evento] = lambda: mock
    app.dependency_overrides[obter_usuario_atual] = lambda: USUARIO_ADMIN
    with TestClient(app) as c:
        yield c, mock
    app.dependency_overrides.clear()


@pytest.fixture
def client_voluntario():
    mock = MagicMock()
    app = FastAPI()
    app.include_router(voluntario_router)
    app.dependency_overrides[get_servico_voluntario] = lambda: mock
    app.dependency_overrides[obter_usuario_atual] = lambda: USUARIO_ADMIN
    with TestClient(app) as c:
        yield c, mock
    app.dependency_overrides.clear()


@pytest.fixture
def client_produto():
    mock = MagicMock()
    app = FastAPI()
    app.include_router(produto_router)
    app.dependency_overrides[get_servico_produto] = lambda: mock
    app.dependency_overrides[obter_usuario_atual] = lambda: USUARIO_ADMIN
    with TestClient(app) as c:
        yield c, mock
    app.dependency_overrides.clear()



ADMIN_VALIDO = {
    "nome": "Admin Teste",
    "email": "admin@teste.com",
    "keycloak_id": "kc-uuid-001",
}
RESPOSTA_ADMIN = {**ADMIN_VALIDO, "admin_id": 1}


@pytest.mark.parametrize("campo_ausente", ["nome", "email", "keycloak_id"])
def test_admin_campo_obrigatorio_ausente_retorna_422(client_admin, campo_ausente):
    c, _ = client_admin
    payload = {k: v for k, v in ADMIN_VALIDO.items() if k != campo_ausente}
    resposta = c.post("/admin/", json=payload)
    assert resposta.status_code == 422


@pytest.mark.parametrize("admin_id", [1, 2, 10, 100])
def test_admin_buscar_varios_ids(client_admin, admin_id):
    c, mock = client_admin
    mock.buscar_admin.return_value = {**RESPOSTA_ADMIN, "admin_id": admin_id}
    resposta = c.get(f"/admin/{admin_id}")
    assert resposta.status_code == 200
    assert resposta.json()["admin_id"] == admin_id



BANDA_VALIDA = {
    "nome": "Banda Teste",
    "link_foto": "https://exemplo.com/foto.jpg",
    "profissao": "Palestrante",
}
RESPOSTA_BANDA = {**BANDA_VALIDA, "participante_id": 1}


@pytest.mark.parametrize("nome", ["DJ Fulano", "Palestrante da Silva", "Banda X"])
def test_banda_criar_varios_nomes(client_banda, nome):
    c, mock = client_banda
    mock.criar_banda_palestrante.return_value = {**RESPOSTA_BANDA, "nome": nome}
    resposta = c.post("/banda-palestrante/", json={**BANDA_VALIDA, "nome": nome})
    assert resposta.status_code == 201
    assert resposta.json()["nome"] == nome


@pytest.mark.parametrize("participante_id", [1, 5, 42, 100])
def test_banda_buscar_varios_ids(client_banda, participante_id):
    c, mock = client_banda
    mock.buscar_banda_palestrante.return_value = {
        **RESPOSTA_BANDA, "participante_id": participante_id
    }
    resposta = c.get(f"/banda-palestrante/{participante_id}")
    assert resposta.status_code == 200
    assert resposta.json()["participante_id"] == participante_id


@pytest.mark.parametrize("participante_id", [1, 2, 3])
def test_banda_deletar_varios_ids(client_banda, participante_id):
    c, mock = client_banda
    mock.deletar_banda_palestrante.return_value = None
    resposta = c.delete(f"/banda-palestrante/{participante_id}")
    assert resposta.status_code == 204



ATIVIDADE_VALIDA = {
    "nome": "Palestra Principal",
    "descricao": "Descrição da palestra",
    "horario_inicio": "2025-06-01T09:00:00",
    "horario_termino": "2025-06-01T10:00:00",
}
RESPOSTA_ATIVIDADE = {**ATIVIDADE_VALIDA, "atividade_id": 1, "evento_id": 1}


@pytest.mark.parametrize("campo_ausente", ["nome", "horario_inicio", "horario_termino"])
def test_atividade_campo_obrigatorio_ausente_retorna_422(client_atividade, campo_ausente):
    c, _ = client_atividade
    payload = {k: v for k, v in ATIVIDADE_VALIDA.items() if k != campo_ausente}
    resposta = c.post("/evento/1/atividade", json=payload)
    assert resposta.status_code == 422


@pytest.mark.parametrize("evento_id", [1, 2, 10])
def test_atividade_criar_em_varios_eventos(client_atividade, evento_id):
    c, mock = client_atividade
    mock.criar_atividade.return_value = {**RESPOSTA_ATIVIDADE, "evento_id": evento_id}
    resposta = c.post(f"/evento/{evento_id}/atividade", json=ATIVIDADE_VALIDA)
    assert resposta.status_code == 201
    assert resposta.json()["evento_id"] == evento_id


@pytest.mark.parametrize("evento_id", [1, 5, 20])
def test_atividade_listar_varios_eventos(client_atividade, evento_id):
    c, mock = client_atividade
    mock.listar_atividades.return_value = []
    resposta = c.get(f"/evento/{evento_id}/atividade")
    assert resposta.status_code == 200
    mock.listar_atividades.assert_called_with(evento_id)


@pytest.mark.parametrize("atividade_id", [1, 3, 7, 50])
def test_atividade_buscar_varios_ids(client_atividade, atividade_id):
    c, mock = client_atividade
    mock.buscar_atividade.return_value = {**RESPOSTA_ATIVIDADE, "atividade_id": atividade_id}
    resposta = c.get(f"/evento/atividade/{atividade_id}")
    assert resposta.status_code == 200
    assert resposta.json()["atividade_id"] == atividade_id


@pytest.mark.parametrize("campo_ausente", ["nome", "horario_inicio", "horario_termino"])
def test_atividade_atualizar_campo_obrigatorio_ausente(client_atividade, campo_ausente):
    c, _ = client_atividade
    payload = {k: v for k, v in ATIVIDADE_VALIDA.items() if k != campo_ausente}
    resposta = c.put("/evento/atividade/1", json=payload)
    assert resposta.status_code == 422


@pytest.mark.parametrize("atividade_id", [1, 2, 5])
def test_atividade_deletar_varios_ids(client_atividade, atividade_id):
    """DELETE /evento/atividade/{id} deve retornar 204."""
    c, mock = client_atividade
    mock.deletar_atividade.return_value = None
    resposta = c.delete(f"/evento/atividade/{atividade_id}")
    assert resposta.status_code == 204


EVENTO_BASE = {
    "nome": "Retiro Teen 2025",
    "descricao": "Retiro anual",
    "local_latitude": -15.7801,
    "local_longitude": -47.9292,
    "data_inicio": "2025-07-10T08:00:00",
    "data_fim": "2025-07-12T18:00:00",
    "link_galeria": None,
    "formulario_link": None,
    "tipo_evento": "Conferência",
}

EVENTO_RESPOSTA = {
    **EVENTO_BASE,
    "evento_id": 1,
    "calendario_evento_id": None,
    "nome_local": None,
}

PAYLOADS_EVENTO_VALIDOS = [
    pytest.param({**EVENTO_BASE}, id="payload_completo"),
    pytest.param(
        {**EVENTO_BASE, "descricao": None, "link_galeria": None},
        id="payload_sem_campos_opcionais",
    ),
    pytest.param(
        {**EVENTO_BASE, "nome": "Encontro Jovem",
         "formulario_link": "https://forms.google.com/123"},
        id="payload_com_formulario",
    ),
]

PAYLOADS_EVENTO_INVALIDOS = [
    pytest.param({}, id="payload_vazio"),
    pytest.param({"nome": "Evento X"}, id="sem_coordenadas_e_datas"),
    pytest.param({**EVENTO_BASE, "local_latitude": "invalido"}, id="latitude_invalida"),
    pytest.param({**EVENTO_BASE, "data_inicio": "data-invalida"}, id="data_invalida"),
]


@pytest.mark.parametrize("payload", PAYLOADS_EVENTO_VALIDOS)
def test_evento_criar_payload_valido(client_evento, payload):
    c, mock = client_evento
    mock.criar_evento.return_value = RespostaEvento(
        **{**payload, "evento_id": 1, "calendario_evento_id": None, "nome_local": None}
    )
    resposta = c.post("/evento/", json=payload)
    assert resposta.status_code == 201
    assert resposta.json()["nome"] == payload["nome"]


@pytest.mark.parametrize("payload", PAYLOADS_EVENTO_INVALIDOS)
def test_evento_criar_payload_invalido_retorna_422(client_evento, payload):
    c, _ = client_evento
    resposta = c.post("/evento/", json=payload)
    assert resposta.status_code == 422



PAYLOADS_VOLUNTARIO_VALIDOS = [
    pytest.param({"nome": "João Silva", "email": "joao@email.com"}, id="payload_minimo"),
    pytest.param(
        {"nome": "Maria Santos", "email": "maria@email.com",
         "resposta_id_formulario": "abc123"},
        id="payload_completo",
    ),
    pytest.param(
        {"nome": "Pedro Costa", "email": "pedro@email.com",
         "resposta_id_formulario": None},
        id="payload_com_formulario_nulo",
    ),
]

PAYLOADS_VOLUNTARIO_INVALIDOS = [
    pytest.param({}, id="payload_vazio"),
    pytest.param({"nome": "João Silva"}, id="sem_email"),
    pytest.param({"email": "joao@email.com"}, id="sem_nome"),
]


@pytest.mark.parametrize("payload", PAYLOADS_VOLUNTARIO_VALIDOS)
def test_voluntario_criar_payload_valido(client_voluntario, payload):
    c, mock = client_voluntario
    mock.criar_voluntario.return_value = RespostaVoluntario(
        **{**payload, "voluntario_id": 1}
    )
    resposta = c.post("/voluntarios/", json=payload)
    assert resposta.status_code == 201
    assert resposta.json()["nome"] == payload["nome"]


@pytest.mark.parametrize("payload", PAYLOADS_VOLUNTARIO_INVALIDOS)
def test_voluntario_criar_payload_invalido_retorna_422(client_voluntario, payload):
    c, _ = client_voluntario
    resposta = c.post("/voluntarios/", json=payload)
    assert resposta.status_code == 422


PAYLOADS_PRODUTO_VALIDOS = [
    pytest.param({"nome": "Camiseta IDB Teen"}, id="payload_minimo"),
    pytest.param(
        {"nome": "E-book Liderança", "descricao": "E-book sobre liderança jovem",
         "link_produto": "https://hotmart.com/ebook"},
        id="payload_completo",
    ),
    pytest.param(
        {"nome": "Livro de Orações", "descricao": None, "link_produto": None},
        id="payload_com_opcionais_nulos",
    ),
]

PAYLOADS_PRODUTO_INVALIDOS = [
    pytest.param({}, id="payload_vazio"),
    pytest.param({"descricao": "Sem nome"}, id="sem_nome"),
]


@pytest.mark.parametrize("payload", PAYLOADS_PRODUTO_VALIDOS)
def test_produto_criar_payload_valido(client_produto, payload):
    c, mock = client_produto
    mock.criar_produto.return_value = RespostaProduto(
        **{**payload, "produto_id": 1,
           "descricao": payload.get("descricao"),
           "link_produto": payload.get("link_produto")}
    )
    resposta = c.post("/produto/", json=payload)
    assert resposta.status_code == 201
    assert resposta.json()["nome"] == payload["nome"]


@pytest.mark.parametrize("payload", PAYLOADS_PRODUTO_INVALIDOS)
def test_produto_criar_payload_invalido_retorna_422(client_produto, payload):
    c, _ = client_produto
    resposta = c.post("/produto/", json=payload)
    assert resposta.status_code == 422