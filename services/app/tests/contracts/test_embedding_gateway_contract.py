"""Contract test for the embedding gateway, ADR 0005 (floor 3, second gateway).

ADR 0005 makes `EmbeddingProvider`, obtained through `get_embedding_provider`,
the only sanctioned path for an embedding. The floor-3 tier (owned by `safety`)
pins *where* that gateway is called by matching calls to
`get_embedding_provider` and `.embed_texts`. That pin is only as good as the
interface it assumes: a new public method (say `embed_query`) or a new backend
would carry embedding calls the call-site check never looks for.

So this test pins the interface itself against the ADR's `python` block:

* `EMBEDDING_PROVIDER_SURFACE` == the public members of `EmbeddingProvider`,
  and no concrete backend adds a public member of its own;
* `EMBEDDING_BACKENDS` == the concrete subclasses, and `get_embedding_provider`
  builds exactly the listed class for each listed backend name;
* `get_embedding_provider` takes no arguments and returns `EmbeddingProvider`
  (no per-user credentials can be handed in — see ADR 0005 §Context).

Changing either side without the other fails here, which is the point.
"""

import ast
import inspect
import os
import re
from pathlib import Path

import pytest

from app.agents import embeddings
from app.agents.embeddings import EmbeddingProvider, get_embedding_provider

APP_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = APP_ROOT.parents[1]
ADR_PATH = REPO_ROOT / "docs" / "adr" / "0005-floor3-embedding-gateway.md"


def _require(path: Path, why: str) -> str:
    """Read a repo doc, failing in CI and skipping elsewhere when absent.

    Same rule as `test_agent_adapter_contract._require`: the API container
    mounts `tests/` but not `docs/`, so locally a missing ADR is a skip; CI has
    the full checkout, so there it is a failure.
    """
    if path.is_file():
        return path.read_text(encoding="utf-8")
    message = f"{path} not found ({why})"
    if os.environ.get("CI"):
        pytest.fail(message)
    pytest.skip(message)


@pytest.fixture(scope="module")
def adr_constants() -> dict[str, object]:
    """Module-level literal assignments in ADR 0005's one `python` block."""
    text = _require(ADR_PATH, "docs/ is not mounted in the container")
    blocks = re.findall(r"^```python\n(.*?)^```", text, flags=re.DOTALL | re.MULTILINE)
    assert len(blocks) == 1, f"expected one python block in ADR 0005, found {len(blocks)}"
    constants: dict[str, object] = {}
    for node in ast.parse(blocks[0]).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                constants[target.id] = ast.literal_eval(node.value)
    return constants


def _public(cls: type) -> set[str]:
    """Public names defined in the class body itself (not inherited)."""
    return {name for name in vars(cls) if not name.startswith("_")}


def _concrete_subclasses(cls: type) -> set[type]:
    out: set[type] = set()
    for sub in cls.__subclasses__():
        if sub.__module__ == embeddings.__name__ and not inspect.isabstract(sub):
            out.add(sub)
        out |= _concrete_subclasses(sub)
    return out


@pytest.fixture
def fresh_factory():
    """Isolate the factory singleton from the rest of the suite."""
    embeddings.reset_embedding_provider()
    yield
    embeddings.reset_embedding_provider()


class TestInterface:
    def test_surface_is_exactly_the_adr(self, adr_constants):
        assert _public(EmbeddingProvider) == adr_constants["EMBEDDING_PROVIDER_SURFACE"], (
            "EmbeddingProvider's public surface changed. A new method is a new way to "
            "embed that floor 3's call-site pins do not see: amend ADR 0005 and ask "
            "`safety` to extend the detector first."
        )

    def test_surface_members_are_all_abstract(self, adr_constants):
        assert EmbeddingProvider.__abstractmethods__ == frozenset(
            adr_constants["EMBEDDING_PROVIDER_SURFACE"]
        )

    def test_no_backend_widens_the_surface(self, adr_constants):
        surface = adr_constants["EMBEDDING_PROVIDER_SURFACE"]
        widened = {
            cls.__name__: sorted(_public(cls) - surface)
            for cls in _concrete_subclasses(EmbeddingProvider)
            if _public(cls) - surface
        }
        assert not widened, f"backend adds public members outside ADR 0005: {widened}"

    def test_factory_signature(self):
        sig = inspect.signature(get_embedding_provider)
        assert not sig.parameters, (
            "get_embedding_provider must take no arguments: the backend is "
            "instance-wide and never per user (ADR 0005)"
        )
        assert sig.return_annotation in (EmbeddingProvider, "EmbeddingProvider")


class TestBackends:
    def test_listed_backends_are_the_concrete_subclasses(self, adr_constants):
        found = {cls.__name__ for cls in _concrete_subclasses(EmbeddingProvider)}
        assert found == set(adr_constants["EMBEDDING_BACKENDS"].values())

    @pytest.mark.parametrize("backend", ["sentence_transformers", "openai", "ollama"])
    def test_factory_builds_the_listed_class(
        self, backend, adr_constants, fresh_factory, monkeypatch
    ):
        from app.config import settings

        expected = getattr(embeddings, adr_constants["EMBEDDING_BACKENDS"][backend])
        dims = {"sentence_transformers": 384, "openai": 1536, "ollama": 768}[backend]
        monkeypatch.setattr(settings, "embedding_backend", backend)
        monkeypatch.setattr(settings, "embedding_dimensions", dims)

        provider = get_embedding_provider()

        assert type(provider) is expected
        assert provider.dimensions == dims

    def test_parametrized_backends_cover_the_adr(self, adr_constants):
        """Keep the parametrize list above in step with the ADR."""
        assert set(adr_constants["EMBEDDING_BACKENDS"]) == {
            "sentence_transformers",
            "openai",
            "ollama",
        }
