"""Pydantic schemas for knowledge graph / concept endpoints."""

from pydantic import BaseModel


class ConceptNode(BaseModel):
    """A concept node in the knowledge graph."""

    id: str
    name: str
    description: str
    category: str
    mention_count: int
    source_weeks: list[int]
    course_id: str
    created_at: str | None = None


class ConceptEdge(BaseModel):
    """An edge (relationship) in the knowledge graph."""

    id: str
    source: str
    target: str
    relation_type: str
    confidence: float


class ConceptGraphResponse(BaseModel):
    """Full knowledge graph for D3 visualization."""

    nodes: list[ConceptNode]
    edges: list[ConceptEdge]


class ConceptRelationItem(BaseModel):
    """A relation in the concept detail view."""

    id: str
    concept_id: str
    concept_name: str
    relation_type: str
    confidence: float


class ConceptDetailResponse(BaseModel):
    """Detailed concept with all relations."""

    id: str
    name: str
    description: str
    category: str
    mention_count: int
    source_artifact_ids: list[str]
    source_weeks: list[int]
    course_id: str
    outgoing_relations: list[ConceptRelationItem]
    incoming_relations: list[ConceptRelationItem]
    created_at: str | None = None
    updated_at: str | None = None


class SimilarConceptItem(BaseModel):
    """A semantically similar concept."""

    id: str
    name: str
    description: str
    category: str
    course_id: str
    similarity: float


class ConceptExtractionResponse(BaseModel):
    """Result of on-demand concept extraction."""

    artifact_id: str
    concept_count: int
    relation_count: int
