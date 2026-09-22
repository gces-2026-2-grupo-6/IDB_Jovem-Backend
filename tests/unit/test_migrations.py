"""
Integridade da cadeia de migrations do Alembic.

Duas branches que criam migration a partir do mesmo ponto geram dois
"heads". O merge das duas nao da conflito no Git — sao arquivos diferentes —
mas "alembic upgrade head" passa a falhar e o deploy para. Hoje isso so
apareceria no job de endpoint do CI, depois de lint, testes e build.

Caso real da Sprint 2: a migration da US05 (26e93df0f2ac) e a da US01
(259093bc4c8e) partem ambas de c3a9f1e2d7b4.

Estes testes leem os arquivos de migrations/versions, sem banco, e rodam no
job de testes comum.
"""

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def scripts():
    config = Config(str(RAIZ / "alembic.ini"))
    config.set_main_option("script_location", str(RAIZ / "migrations"))
    return ScriptDirectory.from_config(config)


def test_existe_um_unico_head(scripts):
    heads = scripts.get_heads()
    assert len(heads) == 1, (
        f"Migrations com {len(heads)} heads: {sorted(heads)}. "
        "Ajuste o down_revision da migration mais nova para apontar para a "
        "outra, ou crie uma migration de merge com 'alembic merge heads'."
    )


def test_toda_revisao_aponta_para_revisao_existente(scripts):
    conhecidas = {rev.revision for rev in scripts.walk_revisions()}
    orfas = []
    for rev in scripts.walk_revisions():
        anteriores = rev.down_revision or ()
        if isinstance(anteriores, str):
            anteriores = (anteriores,)
        orfas += [(rev.revision, ant) for ant in anteriores if ant not in conhecidas]
    assert not orfas, f"down_revision inexistente: {orfas}"


def test_existe_uma_unica_base(scripts):
    assert len(scripts.get_bases()) == 1
