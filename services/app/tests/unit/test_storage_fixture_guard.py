"""A patched `data_dir` must actually take effect (GL#5).

`get_storage()` memoises, so patching `settings.data_dir` after the singleton
exists changes nothing. Twelve fixtures across eight files did exactly that:
each *looked* isolated, and the isolation came entirely from the rootdir
conftest's `DATA_DIR` floor (#100).

That is worse than no fixture. A reader who sees a `tempfile.TemporaryDirectory`
next to a `data_dir` patch concludes the test has its own root and stops asking —
which is precisely how the real answer stayed hidden.

This guard fails on a reintroduction rather than on the twelve that existed,
which are now `isolated_storage()`.
"""

import ast
import pathlib

import pytest

TESTS_ROOT = pathlib.Path(__file__).resolve().parents[1]

#: `tests/unit/core/test_data_dir_isolation.py` patches `data_dir` to assert the
#: floor's own behaviour — that a non-temp root is *refused*. Resetting the
#: storage singleton there would be beside the point, and building one is what
#: the test is checking does not happen.
EXEMPT = {"tests/unit/core/test_data_dir_isolation.py"}


def _patches_data_dir(node: ast.Call) -> bool:
    """True for `patch("...settings.data_dir", ...)` or `patch.object(settings, "data_dir", ...)`."""
    func = node.func
    name = (
        func.attr
        if isinstance(func, ast.Attribute)
        else func.id
        if isinstance(func, ast.Name)
        else ""
    )
    if name not in ("patch", "object"):
        return False
    for arg in node.args:
        if (
            isinstance(arg, ast.Constant)
            and isinstance(arg.value, str)
            and (arg.value == "data_dir" or arg.value.endswith(".data_dir"))
        ):
            return True
    return False


def _collect_offenders() -> list[str]:
    offenders = []
    for path in sorted(TESTS_ROOT.rglob("*.py")):
        rel = str(path.relative_to(TESTS_ROOT.parent))
        if rel in EXEMPT:
            continue
        source = path.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _patches_data_dir(node):
                continue
            # Look at the enclosing function: the reset has to be somewhere in
            # the same scope, whether called directly or via `isolated_storage`.
            scope = _enclosing_scope(tree, node)
            body = ast.get_source_segment(source, scope) if scope else source
            if "reset_storage" not in (body or "") and "isolated_storage" not in (body or ""):
                offenders.append(f"{rel}:{node.lineno}")
    return offenders


def _enclosing_scope(tree: ast.AST, target: ast.AST) -> ast.AST | None:
    best = None
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.lineno <= target.lineno <= (node.end_lineno or node.lineno)
            and (best is None or node.lineno > best.lineno)
        ):
            best = node
    return best


class TestPatchedDataDirTakesEffect:
    def test_no_fixture_patches_data_dir_without_resetting_storage(self):
        offenders = _collect_offenders()

        assert not offenders, (
            "These patch `settings.data_dir` without resetting the storage "
            "singleton, so the patch is a silent no-op and the isolation they "
            "appear to provide comes from the rootdir DATA_DIR floor instead. "
            "Use `isolated_storage()` from tests/conftest.py:\n  " + "\n  ".join(offenders)
        )

    def test_the_guard_can_actually_see_a_violation(self):
        """A guard nobody has watched fail is worth nothing.

        Parses the exact shape it exists to catch and asserts it is flagged, so
        an AST change that quietly stops matching cannot leave this passing
        vacuously.
        """
        source = (
            "def client():\n"
            "    with tempfile.TemporaryDirectory() as d, "
            'patch("app.config.settings.data_dir", d):\n'
            "        yield\n"
        )
        tree = ast.parse(source)
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and _patches_data_dir(n)]

        assert len(calls) == 1
        scope = _enclosing_scope(tree, calls[0])
        body = ast.get_source_segment(source, scope)
        assert "reset_storage" not in body and "isolated_storage" not in body

    @pytest.mark.parametrize("exempt", sorted(EXEMPT))
    def test_exempt_files_still_exist(self, exempt):
        """An exemption for a deleted file silently widens the guard."""
        assert (TESTS_ROOT.parent / exempt).exists()
