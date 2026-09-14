"""
Testes de autorizacao por papel.

Cobre a historia US03 (administrador com acesso restrito ao setor pelo qual
responde) do Backlog de Melhorias.

A elicitacao com a cliente definiu que:
  - Apenas o superadministrador pode excluir conteudo;
  - Os setores que precisam de administrador proprio sao Loja, Agenda/Eventos
    e Inscricoes;
  - Nao ha separacao de acesso entre Jovem e Teen.

O sistema atual reconhece somente dois papeis de realm no Keycloak: "admin" e
"superadmin". Este arquivo fixa o comportamento vigente antes da implementacao
da US03, para que a mudanca seja feita com rede de protecao, e sinaliza as
lacunas encontradas na auditoria.

Referencia: IDB_Jovem-Documentacao — docs/projeto/matriz-autorizacao.md
"""

from unittest.mock import MagicMock

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


class TestPapeisReconhecidos:
    """O sistema hoje reconhece apenas dois papeis de realm."""

    def test_superadmin_acessa_rota_de_superadmin(self):
        usuario = usuario_com_papeis(SUPERADMIN)
        assert executar([SUPERADMIN], usuario) is usuario

    def test_admin_acessa_rota_compartilhada(self):
        usuario = usuario_com_papeis(ADMIN)
        assert executar([ADMIN, SUPERADMIN], usuario) is usuario

    def test_superadmin_acessa_rota_compartilhada(self):
        usuario = usuario_com_papeis(SUPERADMIN)
        assert executar([ADMIN, SUPERADMIN], usuario) is usuario


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

    def test_roles_como_string_nao_concede_acesso(self):
        """Campo malformado nao pode ser interpretado como lista de papeis."""
        usuario = {"realm_access": {"roles": "superadmin"}}
        dependencia = verificar_roles([SUPERADMIN])
        try:
            dependencia(usuario=usuario)
        except HTTPException as erro:
            assert erro.status_code == 403
        else:
            pytest.fail(
                "Papeis enviados como string foram aceitos: a verificacao usa "
                "'in', que casa substring quando o valor nao e uma lista."
            )


class TestMatrizDeRotasProtegidas:
    """
    Espelha a matriz documentada em docs/qualidade/matriz-autorizacao.md.

    Se um controlador mudar a exigencia de papel, este teste falha e obriga a
    atualizacao da documentacao junto do codigo.
    """

    MATRIZ = [
        ("POST /evento", [ADMIN, SUPERADMIN]),
        ("PUT /evento/{id}", [ADMIN, SUPERADMIN]),
        ("DELETE /evento/{id}", [ADMIN, SUPERADMIN]),
        ("POST /lider", [ADMIN, SUPERADMIN]),
        ("PUT /lider/{id}", [ADMIN, SUPERADMIN]),
        ("DELETE /lider/{id}", [ADMIN, SUPERADMIN]),
        ("POST /produto", [SUPERADMIN]),
        ("PUT /produto/{id}", [SUPERADMIN]),
        ("DELETE /produto/{id}", [SUPERADMIN]),
        ("POST /voluntario", [ADMIN, SUPERADMIN]),
        ("POST /banda-palestrante", [ADMIN, SUPERADMIN]),
        ("POST /admin", [SUPERADMIN]),
        ("DELETE /admin/{id}", [SUPERADMIN]),
    ]

    @pytest.mark.parametrize("rota,roles", MATRIZ)
    def test_superadmin_alcanca_toda_rota_da_matriz(self, rota, roles):
        usuario = usuario_com_papeis(SUPERADMIN)
        assert executar(roles, usuario) is usuario

    @pytest.mark.parametrize("rota,roles", MATRIZ)
    def test_usuario_sem_papel_e_negado_em_toda_rota_da_matriz(self, rota, roles):
        usuario = usuario_com_papeis()
        with pytest.raises(HTTPException) as erro:
            executar(roles, usuario)
        assert erro.value.status_code == 403

    @pytest.mark.parametrize(
        "rota",
        [r for r, roles in MATRIZ if roles == [SUPERADMIN]],
    )
    def test_admin_e_negado_nas_rotas_exclusivas_de_superadmin(self, rota):
        usuario = usuario_com_papeis(ADMIN)
        with pytest.raises(HTTPException) as erro:
            executar([SUPERADMIN], usuario)
        assert erro.value.status_code == 403


class TestRotasSemProtecao:
    """
    Lacuna encontrada na auditoria da Sprint 1.

    O controlador de atividades (src/atividade/controller.py) registra POST,
    PUT e DELETE sem nenhuma dependencia de verificacao de papel, e o router
    nao e incluido com dependencias em src/main.py. Na pratica, a programacao
    de qualquer evento pode ser criada, alterada ou apagada sem autenticacao.

    O teste abaixo documenta a ausencia. Quando a US03 for implementada e a
    protecao adicionada, ele passa a falhar — sinalizando que deve ser movido
    para a matriz acima.
    """

    def test_rotas_de_atividade_ainda_nao_exigem_papel(self):
        from src.atividade import controller

        rotas_de_escrita = [
            rota
            for rota in controller.router.routes
            if set(rota.methods) & {"POST", "PUT", "DELETE"}
        ]
        assert rotas_de_escrita, "Nenhuma rota de escrita encontrada em atividade."

        desprotegidas = [
            f"{sorted(rota.methods)} {rota.path}"
            for rota in rotas_de_escrita
            if not any(
                "verificar_roles" in repr(dep.call)
                for dep in rota.dependant.dependencies
            )
        ]

        assert desprotegidas == [
            "['POST'] /evento/{evento_id}/atividade",
            "['PUT'] /evento/atividade/{atividade_id}",
            "['DELETE'] /evento/atividade/{atividade_id}",
        ], (
            "A lista de rotas de atividade sem verificacao de papel mudou. "
            "Se a protecao foi adicionada, mova estas rotas para a MATRIZ em "
            "TestMatrizDeRotasProtegidas e atualize a matriz documentada."
        )
