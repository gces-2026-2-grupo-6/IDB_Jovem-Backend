"""
Token com papeis em formato inesperado nas duas guardas de src/security.py.

A QA05 corrigiu verificar_roles para roles enviado como string. A guarda de
setor, criada depois pela US03, e os demais formatos ficaram de fora: com
roles None, ou realm_access fora do formato, a leitura levantava excecao e a
rota respondia 500 em vez de 403.

Regra: todo payload fora do formato vira 403 — nunca acesso, nunca 500.
"""

import pytest
from fastapi import HTTPException

from src.security import verificar_permissao_setor, verificar_roles

PAYLOADS_MALFORMADOS = [
    pytest.param({"realm_access": {"roles": "superadmin"}}, id="roles-string"),
    pytest.param({"realm_access": {"roles": None}}, id="roles-none"),
    pytest.param({"realm_access": {"roles": {"superadmin": True}}}, id="roles-dict"),
    pytest.param({"realm_access": {"roles": [["superadmin"]]}}, id="roles-aninhado"),
    pytest.param({"realm_access": None}, id="realm-none"),
    pytest.param({"realm_access": "superadmin"}, id="realm-string"),
    pytest.param({}, id="sem-realm"),
]

GUARDAS = [
    pytest.param(lambda: verificar_roles(["superadmin"]), id="verificar_roles"),
    pytest.param(lambda: verificar_permissao_setor("eventos"), id="setor-eventos"),
]


@pytest.mark.parametrize("fabrica", GUARDAS)
@pytest.mark.parametrize("usuario", PAYLOADS_MALFORMADOS)
def test_payload_malformado_resulta_em_403(fabrica, usuario):
    with pytest.raises(HTTPException) as erro:
        fabrica()(usuario=usuario)
    assert erro.value.status_code == 403


@pytest.mark.parametrize("fabrica", GUARDAS)
def test_papeis_validos_continuam_aceitos(fabrica):
    usuario = {"realm_access": {"roles": ("superadmin",)}}
    assert fabrica()(usuario=usuario) is usuario
