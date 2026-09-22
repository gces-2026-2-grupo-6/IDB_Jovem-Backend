"""
Testes de autorizacao por papel.

Cobre a historia US03 (administrador com acesso restrito ao setor pelo qual
responde) do Backlog de Melhorias.

A elicitacao com a cliente definiu que:
  - Apenas o superadministrador pode excluir conteudo;
  - Os setores que precisam de administrador proprio sao Loja, Agenda/Eventos
    e Inscricoes;
  - Nao ha separacao de acesso entre Jovem e Teen.

Este arquivo cobre o que a verificacao de papeis NAO pode aceitar: negacao
de acesso e tentativas de escalonamento de privilegio.

O restante da autorizacao fica em:
  - tests/unit/test_matriz_rotas.py     exigencia de cada rota, lida do codigo
  - tests/unit/test_token_malformado.py papeis em formato inesperado
  - tests/unit/test_security.py         leitura do token e as duas guardas
  - tests/unit/test_autorizacao_setores.py  setores via HTTP

Referencia: IDB_Jovem-Documentacao — docs/projeto/matriz-autorizacao.md
"""

import pytest
from fastapi import HTTPException

from src.security import verificar_roles

ADMIN = "admin"
SUPERADMIN = "superadmin"


def usuario_com_papeis(*papeis):
    """Monta o payload de token que o Keycloak devolveria para esses papeis."""
    return {"realm_access": {"roles": list(papeis)}}


def executar(roles_exigidas, usuario):
    """Executa a dependencia de autorizacao fora do ciclo do FastAPI."""
    dependencia = verificar_roles(roles_exigidas)
    return dependencia(usuario=usuario)


class TestNegacaoDeAcesso:
    """Toda tentativa fora do papel deve resultar em 403."""

    def test_admin_nao_acessa_rota_exclusiva_de_superadmin(self):
        """US03 — a cliente definiu que so o superadmin exclui conteudo."""
        usuario = usuario_com_papeis(ADMIN)
        with pytest.raises(HTTPException) as erro:
            executar([SUPERADMIN], usuario)
        assert erro.value.status_code == 403

    def test_usuario_sem_papel_e_negado(self):
        usuario = usuario_com_papeis()
        with pytest.raises(HTTPException) as erro:
            executar([ADMIN, SUPERADMIN], usuario)
        assert erro.value.status_code == 403

    def test_token_sem_realm_access_e_negado(self):
        """Token malformado nao pode ser tratado como autorizado."""
        with pytest.raises(HTTPException) as erro:
            executar([ADMIN], {})
        assert erro.value.status_code == 403

    def test_papel_desconhecido_nao_concede_acesso(self):
        """Papel inventado no token nao pode abrir porta."""
        usuario = usuario_com_papeis("editor", "gerente", "root")
        with pytest.raises(HTTPException) as erro:
            executar([ADMIN, SUPERADMIN], usuario)
        assert erro.value.status_code == 403

    def test_mensagem_de_erro_nao_vaza_papeis_alheios(self):
        """A mensagem informa o que era exigido, nao o que o usuario possui."""
        usuario = usuario_com_papeis("editor")
        with pytest.raises(HTTPException) as erro:
            executar([SUPERADMIN], usuario)
        assert "editor" not in erro.value.detail


class TestEscalonamentoDePrivilegio:
    """Tentativas de obter acesso alem do papel concedido."""

    def test_papel_semelhante_nao_e_aceito(self):
        """"administrador" nao pode passar por "admin"."""
        usuario = usuario_com_papeis("administrador")
        with pytest.raises(HTTPException):
            executar([ADMIN], usuario)

    def test_diferenca_de_caixa_nao_e_aceita(self):
        """A comparacao e sensivel a maiusculas — "Admin" nao e "admin"."""
        usuario = usuario_com_papeis("Admin", "SUPERADMIN")
        with pytest.raises(HTTPException):
            executar([ADMIN, SUPERADMIN], usuario)

    def test_papel_em_resource_access_nao_substitui_realm_access(self):
        """Papel de cliente nao pode valer como papel de realm."""
        usuario = {
            "realm_access": {"roles": []},
            "resource_access": {"jovem-backend": {"roles": [SUPERADMIN]}},
        }
        with pytest.raises(HTTPException):
            executar([SUPERADMIN], usuario)
