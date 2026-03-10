"""Tests for concept extraction parsing and prompt building."""

import pytest

from app.agents.base import ConceptExtractionResult
from app.agents.parsing import (
    VALID_CONCEPT_CATEGORIES,
    VALID_RELATION_TYPES,
    parse_concept_extraction_response,
)
from app.core.exceptions import AgentError


class TestParseConceptExtractionResponse:
    """Tests for parse_concept_extraction_response."""

    def test_parses_valid_json(self):
        """Parses a well-formed concept extraction response."""
        text = """{
            "concepts": [
                {"name": "Binary Search", "description": "Search algorithm for sorted arrays", "category": "algorithm"},
                {"name": "Divide and Conquer", "description": "Problem-solving paradigm", "category": "pattern"}
            ],
            "relations": [
                {"source": "Binary Search", "target": "Divide and Conquer", "relation_type": "uses", "confidence": 0.9}
            ]
        }"""
        result = parse_concept_extraction_response(text)

        assert isinstance(result, ConceptExtractionResult)
        assert len(result.concepts) == 2
        assert result.concepts[0].name == "Binary Search"
        assert result.concepts[0].category == "algorithm"
        assert len(result.relations) == 1
        assert result.relations[0].source == "Binary Search"
        assert result.relations[0].confidence == 0.9

    def test_parses_json_in_code_fence(self):
        """Extracts JSON from markdown code fences."""
        text = """Sure, here are the concepts:
```json
{
    "concepts": [{"name": "Hash Table", "description": "Key-value store", "category": "data_structure"}],
    "relations": []
}
```"""
        result = parse_concept_extraction_response(text)
        assert len(result.concepts) == 1
        assert result.concepts[0].name == "Hash Table"

    def test_handles_empty_response(self):
        """Returns empty result for empty JSON."""
        text = '{"concepts": [], "relations": []}'
        result = parse_concept_extraction_response(text)
        assert result.concepts == []
        assert result.relations == []

    def test_normalizes_invalid_category(self):
        """Invalid categories are normalized to 'general'."""
        text = '{"concepts": [{"name": "Test", "description": "desc", "category": "invalid_cat"}], "relations": []}'
        result = parse_concept_extraction_response(text)
        assert result.concepts[0].category == "general"

    def test_normalizes_invalid_relation_type(self):
        """Invalid relation types are normalized to 'related_to'."""
        text = '{"concepts": [], "relations": [{"source": "A", "target": "B", "relation_type": "blah", "confidence": 0.5}]}'
        result = parse_concept_extraction_response(text)
        assert result.relations[0].relation_type == "related_to"

    def test_clamps_confidence(self):
        """Confidence is clamped to [0.0, 1.0]."""
        text = '{"concepts": [], "relations": [{"source": "A", "target": "B", "relation_type": "uses", "confidence": 1.5}]}'
        result = parse_concept_extraction_response(text)
        assert result.relations[0].confidence == 1.0

    def test_skips_concepts_without_name(self):
        """Concepts with empty name are skipped."""
        text = '{"concepts": [{"name": "", "description": "no name", "category": "general"}, {"name": "Valid", "description": "ok", "category": "general"}], "relations": []}'
        result = parse_concept_extraction_response(text)
        assert len(result.concepts) == 1
        assert result.concepts[0].name == "Valid"

    def test_skips_relations_without_source_or_target(self):
        """Relations with missing source/target are skipped."""
        text = '{"concepts": [], "relations": [{"source": "", "target": "B", "relation_type": "uses", "confidence": 0.5}, {"source": "A", "target": "", "relation_type": "uses", "confidence": 0.5}]}'
        result = parse_concept_extraction_response(text)
        assert len(result.relations) == 0

    def test_raises_on_unparseable(self):
        """Raises AgentError on completely unparseable text."""
        with pytest.raises(AgentError):
            parse_concept_extraction_response("This is not JSON at all")


class TestValidConstants:
    """Verify that valid categories and relation types are consistent."""

    def test_valid_categories(self):
        """All expected categories are present."""
        expected = {
            "theory",
            "algorithm",
            "data_structure",
            "pattern",
            "tool",
            "language",
            "protocol",
            "principle",
            "method",
            "general",
        }
        assert expected == VALID_CONCEPT_CATEGORIES

    def test_valid_relation_types(self):
        """All expected relation types are present."""
        expected = {"prerequisite", "extends", "uses", "related_to", "part_of"}
        assert expected == VALID_RELATION_TYPES
