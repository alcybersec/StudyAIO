"""Tests for concept embedding generation.

Concept embeddings were never generated: `concept_service` imported
`app.services.embedding_service`, a module that does not exist, and called
`provider.embed()`, a method `EmbeddingProvider` does not declare. A bare
`except Exception` swallowed both, so every concept carried a NULL embedding and
`GET /api/concepts/{id}/similar` returned `[]` for every concept, forever,
without ever erroring. See issue #33.

These tests exist to make that class of failure loud.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.models.concept import Concept
from app.services.concept_service import _embed_concepts


def _concept(name: str) -> Concept:
    return Concept(id=name, name=name, description=f"description of {name}", embedding=None)


def test_embeddings_are_attached():
    concepts = [_concept("tls"), _concept("kerberos")]
    provider = MagicMock()
    provider.embed_texts.return_value = [[0.1] * 384, [0.2] * 384]

    with patch("app.agents.embeddings.get_embedding_provider", return_value=provider):
        _embed_concepts(concepts)

    assert concepts[0].embedding == [0.1] * 384
    assert concepts[1].embedding == [0.2] * 384


def test_the_provider_is_called_once_for_the_whole_batch():
    """One provider call, not one per concept — the model pays per call."""
    concepts = [_concept("a"), _concept("b"), _concept("c")]
    provider = MagicMock()
    provider.embed_texts.return_value = [[0.0] * 384] * 3

    with patch("app.agents.embeddings.get_embedding_provider", return_value=provider):
        _embed_concepts(concepts)

    provider.embed_texts.assert_called_once()
    assert provider.embed_texts.call_args.args[0] == [
        "a: description of a",
        "b: description of b",
        "c: description of c",
    ]


def test_the_declared_interface_method_is_used():
    """`embed_texts` is what the ABC declares; `embed` is not.

    Calling a method the interface does not have is the second half of #33.
    A MagicMock would happily answer either, so assert on the real name.
    """
    provider = MagicMock(spec=["embed_texts", "dimensions"])
    provider.embed_texts.return_value = [[0.0] * 384]

    with patch("app.agents.embeddings.get_embedding_provider", return_value=provider):
        _embed_concepts([_concept("x")])

    provider.embed_texts.assert_called_once()


def test_a_provider_failure_is_tolerated():
    """A provider that is down must not lose the extracted concepts."""
    concepts = [_concept("tls")]
    provider = MagicMock()
    provider.embed_texts.side_effect = ConnectionError("provider unreachable")

    with patch("app.agents.embeddings.get_embedding_provider", return_value=provider):
        _embed_concepts(concepts)

    assert concepts[0].embedding is None


@pytest.mark.parametrize(
    "programming_error",
    [ImportError("no such module"), AttributeError("no such method"), TypeError("bad signature")],
)
def test_programming_errors_are_not_swallowed(programming_error):
    """The exact failures #33 hid must now propagate.

    A missing module, a method that is not there, a bad signature — these are
    defects in this code, not a provider having a bad day. Swallowing them is
    what let the feature ship broken and stay broken.
    """
    provider = MagicMock()
    provider.embed_texts.side_effect = programming_error

    with patch("app.agents.embeddings.get_embedding_provider", return_value=provider):
        with pytest.raises(type(programming_error)):
            _embed_concepts([_concept("tls")])


def test_a_short_response_is_refused_rather_than_misaligned():
    """Fewer vectors than concepts would silently mislabel every one after the gap."""
    concepts = [_concept("a"), _concept("b"), _concept("c")]
    provider = MagicMock()
    provider.embed_texts.return_value = [[0.1] * 384, [0.2] * 384]

    with patch("app.agents.embeddings.get_embedding_provider", return_value=provider):
        _embed_concepts(concepts)

    assert all(c.embedding is None for c in concepts)


class TestWiring:
    """The helper must actually be reached from the extraction path.

    Every test above passes with the call removed from
    `extract_and_save_concepts`, which is the shape of the original bug: correct
    code that nothing invokes.
    """

    @pytest.mark.asyncio
    @patch("app.agents.factory.get_agent")
    async def test_extraction_embeds_the_concepts_it_creates(self, mock_get_agent, mock_session):
        from unittest.mock import AsyncMock

        from app.agents.base import ConceptData, ConceptExtractionResult
        from app.services.concept_service import extract_and_save_concepts

        agent = MagicMock()
        agent.extract_concepts = AsyncMock(
            return_value=ConceptExtractionResult(
                concepts=[
                    ConceptData(name="TLS", description="Transport security", category="net")
                ],
                relations=[],
            )
        )
        mock_get_agent.return_value = agent

        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                all=MagicMock(return_value=[]),
                scalar_one_or_none=MagicMock(return_value=None),
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
            )
        )
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()

        with patch("app.services.concept_service._embed_concepts") as embed:
            await extract_and_save_concepts(
                session=mock_session,
                artifact_id="art-001",
                user_id="user-001",
                course_id="course-001",
                week=1,
                extraction_text="TLS provides confidentiality...",
            )

        embed.assert_called_once()
        embedded = embed.call_args.args[0]
        assert [c.name for c in embedded] == ["TLS"]
