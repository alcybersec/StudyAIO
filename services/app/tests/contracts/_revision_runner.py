"""Find an Alembic revision newer than a given one and run it on scratch SQLite.

Shared by the SEC-013 and SEC-014 contract tests (``models.secrets-at-rest v2``,
``models.telegram-pairing-code v1``). Both revisions are data-only (Core
``UPDATE`` statements, no type change), so they run unchanged on an in-memory
SQLite database with the handful of columns they touch. That checks what the
revision *does* to rows, not how its source is spelled. Not a test module (no
``test_`` prefix), so pytest does not collect it.
"""

import ast
import inspect
from collections.abc import Callable
from types import ModuleType

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from tests.contracts._weakspot_docs import APP_ROOT

#: Head of the revision graph when SEC-013/014 were specified (``711f591``).
BASE_REVISION = "b2d4f6a8c0e1"

METADATA = sa.MetaData()

OAUTH_ACCOUNTS = sa.Table(
    "oauth_accounts",
    METADATA,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("user_id", sa.String(36), nullable=False),
    sa.Column("provider", sa.String(50), nullable=False),
    sa.Column("provider_user_id", sa.String(255), nullable=False),
    sa.Column("access_token", sa.Text, nullable=True),
    sa.Column("refresh_token", sa.Text, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
)

TELEGRAM_LINKS = sa.Table(
    "telegram_links",
    METADATA,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("user_id", sa.String(36), nullable=False),
    sa.Column("chat_id", sa.BigInteger, nullable=True),
    sa.Column("username", sa.String(255), nullable=True),
    sa.Column("verified", sa.Boolean, nullable=False, default=False),
    sa.Column("link_token", sa.String(64), nullable=True, unique=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
)


def newer_revisions() -> list[ModuleType]:
    """Every revision module strictly after ``BASE_REVISION``, newest first."""
    script = ScriptDirectory(str(APP_ROOT / "alembic"))
    return [
        rev.module
        for rev in script.iterate_revisions("heads", BASE_REVISION)
        if rev.revision != BASE_REVISION
    ]


def _inlined(module: ModuleType, name: str) -> str:
    """Source of ``name`` plus every module-level helper it calls, one level deep."""
    tree = ast.parse(inspect.getsource(module))
    funcs = {n.name: ast.unparse(n) for n in tree.body if isinstance(n, ast.FunctionDef)}
    source = funcs.get(name, "")
    called = {
        n.func.id
        for n in ast.walk(ast.parse(source or "pass"))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    return "\n".join([source, *(funcs[c] for c in sorted(called & set(funcs)) if c != name)])


def find_revision(table: str, owner: str) -> ModuleType:
    """The one revision after ``BASE_REVISION`` whose upgrade touches ``table``."""
    hits = [m for m in newer_revisions() if table in _inlined(m, "upgrade")]
    assert hits, f"no Alembic revision after {BASE_REVISION} touches {table} (`{owner}`)"
    assert len(hits) == 1, f"more than one revision touches {table}: {[m.__name__ for m in hits]}"
    return hits[0]


def scratch_engine(seed: Callable[[sa.Connection], None]) -> sa.Engine:
    """In-memory SQLite with both tables created and ``seed`` applied."""
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        METADATA.create_all(conn)
        seed(conn)
    return engine


def run(engine: sa.Engine, module: ModuleType, direction: str) -> None:
    """Run ``module.upgrade`` or ``module.downgrade`` against ``engine``."""
    with engine.begin() as conn:
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            getattr(module, direction)()


def rows(engine: sa.Engine, table: sa.Table) -> list[dict]:
    """Every row of ``table`` as a dict, ordered by id."""
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(sa.select(table).order_by(table.c.id))]
