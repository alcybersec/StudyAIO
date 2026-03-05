"""API routes for knowledge graph / concepts."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.concept_schemas import (
    ConceptDetailResponse,
    ConceptEdge,
    ConceptExtractionResponse,
    ConceptGraphResponse,
    ConceptNode,
    ConceptRelationItem,
    SimilarConceptItem,
)
from app.api.deps import get_current_user_or_default
from app.core.database import get_session
from app.core.rate_limit import limiter
from app.models.course import Course
from app.models.user import User
from app.services import concept_service

logger = structlog.get_logger()

router = APIRouter()


async def _resolve_course_id(
    session: AsyncSession, course_code: str | None, user_id: str
) -> str | None:
    """Resolve a course_code to a course_id, scoped to user."""
    if not course_code:
        return None
    result = await session.execute(
        select(Course.id).where(Course.code == course_code, Course.user_id == user_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail=f"Course '{course_code}' not found")
    return row


@router.get(
    "/concepts/graph",
    response_model=ConceptGraphResponse,
    summary="Get knowledge graph",
    description="Returns all concept nodes and edges for D3 force-directed graph visualization.",
)
@limiter.limit("30/minute")
async def get_concept_graph(
    request: Request,
    course_code: str | None = Query(None, description="Filter by course code"),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> ConceptGraphResponse:
    """Get the knowledge graph (nodes + edges)."""
    course_id = await _resolve_course_id(session, course_code, user.id)
    graph = await concept_service.get_concept_graph(session, user.id, course_id=course_id)

    return ConceptGraphResponse(
        nodes=[ConceptNode(**n) for n in graph["nodes"]],
        edges=[ConceptEdge(**e) for e in graph["edges"]],
    )


@router.get(
    "/concepts",
    response_model=list[ConceptNode],
    summary="List concepts",
    description="List all concepts with optional course and search filters.",
)
@limiter.limit("30/minute")
async def list_concepts(
    request: Request,
    course_code: str | None = Query(None, description="Filter by course code"),
    search: str | None = Query(None, description="Search by name or description"),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> list[ConceptNode]:
    """List concepts with optional filters."""
    course_id = await _resolve_course_id(session, course_code, user.id)
    concepts = await concept_service.get_concepts(
        session, user.id, course_id=course_id, search=search
    )
    return [ConceptNode(**c) for c in concepts]


@router.get(
    "/concepts/{concept_id}",
    response_model=ConceptDetailResponse,
    summary="Get concept detail",
    description="Returns a concept with all incoming and outgoing relations.",
)
@limiter.limit("30/minute")
async def get_concept_detail(
    concept_id: str,
    request: Request,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> ConceptDetailResponse:
    """Get detailed concept info with relations."""
    detail = await concept_service.get_concept_detail(session, concept_id, user.id)
    if not detail:
        raise HTTPException(status_code=404, detail="Concept not found")

    return ConceptDetailResponse(
        id=detail["id"],
        name=detail["name"],
        description=detail["description"],
        category=detail["category"],
        mention_count=detail["mention_count"],
        source_artifact_ids=detail["source_artifact_ids"],
        source_weeks=detail["source_weeks"],
        course_id=detail["course_id"],
        outgoing_relations=[
            ConceptRelationItem(
                id=r["id"],
                concept_id=r["target_id"],
                concept_name=r["target_name"],
                relation_type=r["relation_type"],
                confidence=r["confidence"],
            )
            for r in detail["outgoing_relations"]
        ],
        incoming_relations=[
            ConceptRelationItem(
                id=r["id"],
                concept_id=r["source_id"],
                concept_name=r["source_name"],
                relation_type=r["relation_type"],
                confidence=r["confidence"],
            )
            for r in detail["incoming_relations"]
        ],
        created_at=detail.get("created_at"),
        updated_at=detail.get("updated_at"),
    )


@router.get(
    "/concepts/{concept_id}/related",
    response_model=list[SimilarConceptItem],
    summary="Find related concepts",
    description="Find semantically similar concepts using embedding similarity.",
)
@limiter.limit("30/minute")
async def find_related_concepts(
    concept_id: str,
    request: Request,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> list[SimilarConceptItem]:
    """Find semantically similar concepts."""
    similar = await concept_service.find_related_concepts(session, concept_id, user.id)
    return [SimilarConceptItem(**s) for s in similar]


@router.post(
    "/concepts/extract/{artifact_id}",
    response_model=ConceptExtractionResponse,
    status_code=201,
    summary="Extract concepts from artifact",
    description="Trigger on-demand concept extraction for a specific artifact.",
)
@limiter.limit("10/minute")
async def extract_concepts(
    artifact_id: str,
    request: Request,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> ConceptExtractionResponse:
    """Trigger concept extraction for an artifact."""
    from app.models.artifact import LectureArtifact
    from app.models.extraction import Extraction

    from app.agents import parsing
    from app.services.summary_service import merge_extractions

    # Verify artifact exists and belongs to user
    result = await session.execute(
        select(LectureArtifact).where(
            LectureArtifact.id == artifact_id,
            LectureArtifact.user_id == user.id,
        )
    )
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    if not artifact.course_id or artifact.week is None:
        raise HTTPException(status_code=400, detail="Artifact not classified yet")

    # Load extraction text
    ext_result = await session.execute(
        select(Extraction).where(Extraction.artifact_id == artifact_id)
    )
    extraction = ext_result.scalar_one_or_none()
    if not extraction:
        raise HTTPException(status_code=400, detail="No extraction found for artifact")

    extraction_data = merge_extractions([extraction])
    extraction_text = parsing.build_extraction_text(extraction_data)

    result = await concept_service.extract_and_save_concepts(
        session=session,
        artifact_id=artifact_id,
        user_id=user.id,
        course_id=artifact.course_id,
        week=artifact.week,
        extraction_text=extraction_text,
    )

    return ConceptExtractionResponse(
        artifact_id=artifact_id,
        concept_count=result["concept_count"],
        relation_count=result["relation_count"],
    )
