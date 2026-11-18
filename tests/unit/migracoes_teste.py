"""
Leitura do que uma migration faz, sem banco.

`test_migrations.py` confere a cadeia (um head, uma base, nenhuma revisao
orfa), mas nao o conteudo: uma migration pode estar bem encadeada e criar a
coluna com outro nome, ou esquecer o `server_default` que um criterio de
aceitacao exige. Aqui o `op` do Alembic e trocado por um mock e as chamadas
de `upgrade()`/`downgrade()` sao registradas, para o teste da historia
comparar com o modelo.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from alembic.config import Config
from alembic.script import ScriptDirectory

RAIZ = Path(__file__).resolve().parents[2]


def _scripts() -> ScriptDirectory:
    config = Config(str(RAIZ / "alembic.ini"))
    config.set_main_option("script_location", str(RAIZ / "migrations"))
    return ScriptDirectory.from_config(config)


def revisao(identificador: str):
    return _scripts().get_revision(identificador)


def operacoes(identificador: str, etapa: str = "upgrade") -> MagicMock:
    """Executa `upgrade` ou `downgrade` da revisao com `op` simulado."""
    modulo = revisao(identificador).module
    op = MagicMock()
    with patch.object(modulo, "op", op):
        getattr(modulo, etapa)()
    return op


def colunas_adicionadas(op: MagicMock, tabela: str) -> dict:
    """{nome: Column} de cada `op.add_column(tabela, Column)` registrado."""
    return {
        chamada.args[1].name: chamada.args[1]
        for chamada in op.add_column.call_args_list
        if chamada.args[0] == tabela
    }


def colunas_removidas(op: MagicMock, tabela: str) -> set[str]:
    return {
        chamada.args[1]
        for chamada in op.drop_column.call_args_list
        if chamada.args[0] == tabela
    }
