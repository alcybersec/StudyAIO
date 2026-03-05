"""Concept service — business logic for knowledge graph extraction and queries."""

import structlog
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.base import ConceptExtractionResult
from app.core.utils import generate_id
from app.models.concept import Concept
from app.models.concept_relation import ConceptRelation

logger = structlog.get_logger()


async def extract_and_save_concepts(
    session: AsyncSession,
    artifact_id: str,
    user_id: str,
    course_id: str,
    week: int,
    extraction_text: str,
) -> dict:
    """Extract concepts from text and save to DB.

    Calls the AI agent to extract concepts and relationships,
    then upserts them into the database (incrementing mention_count
    for existing concepts).

    Args:
        session: Async DB session.
        artifact_id: Source artifact ID.
        user_id: Owner user ID.
        course_id: Course ID.
        week: Week number.
        extraction_text: Text content to analyze.

    Returns:
        Dict with concept_count and relation_count.
    """
    # Get existing concept names for this course
    existing_result = await session.execute(
        select(Concept.name).where(
            Concept.user_id == user_id,
            Concept.course_id == course_id,
        )
    )
    existing_names = [row[0] for row in existing_result.all()]

    # Call AI agent (lazy import to avoid circular deps)
    from app.agents.factory import get_agent

    agent = get_agent()
    ai_result: ConceptExtractionResult = await agent.extract_concepts(
        text=extraction_text,
        existing_concepts=existing_names if existing_names else None,
    )

    # Upsert concepts
    concept_map: dict[str, Concept] = {}
    for concept_data in ai_result.concepts:
        name_lower = concept_data.name.lower()

        # Check if concept already exists
        existing = await session.execute(
            select(Concept).where(
                Concept.user_id == user_id,
                Concept.course_id == course_id,
                func.lower(Concept.name) == name_lower,
            )
        )
        concept = existing.scalar_one_or_none()

        if concept:
            # Update existing concept
            concept.mention_count += 1
            if artifact_id not in (concept.source_artifact_ids or []):
                concept.source_artifact_ids = [
                    *(concept.source_artifact_ids or []),
                    artifact_id,
                ]
            if week not in (concept.source_weeks or []):
                concept.source_weeks = [*(concept.source_weeks or []), week]
            # Update description if new one is longer
            if len(concept_data.description) > len(concept.description):
                concept.description = concept_data.description
        else:
            concept = Concept(
                id=generate_id(),
                user_id=user_id,
                course_id=course_id,
                name=concept_data.name,
                description=concept_data.description,
                category=concept_data.category,
                source_artifact_ids=[artifact_id],
                source_weeks=[week],
                mention_count=1,
            )
            session.add(concept)

        concept_map[name_lower] = concept

    await session.flush()

    # Generate embeddings for new concepts (best-effort)
    try:
        from app.services.embedding_service import get_embedding_provider

        provider = get_embedding_provider()
        for concept in concept_map.values():
            if concept.embedding is None:
                embed_text = f"{concept.name}: {concept.description}"
                embedding = await provider.embed(embed_text)
                concept.embedding = embedding
    except Exception:
        logger.warning("concept_embedding_failed", exc_info=True)

    # Save relations (dedup by unique constraint)
    relation_count = 0
    for rel_data in ai_result.relations:
        source_key = rel_data.source.lower()
        target_key = rel_data.target.lower()

        source_concept = concept_map.get(source_key)
        target_concept = concept_map.get(target_key)

        # If source/target not in current extraction, look up in DB
        if not source_concept:
            result = await session.execute(
                select(Concept).where(
                    Concept.user_id == user_id,
                    Concept.course_id == course_id,
                    func.lower(Concept.name) == source_key,
                )
            )
            source_concept = result.scalar_one_or_none()

        if not target_concept:
            result = await session.execute(
                select(Concept).where(
                    Concept.user_id == user_id,
                    Concept.course_id == course_id,
                    func.lower(Concept.name) == target_key,
                )
            )
            target_concept = result.scalar_one_or_none()

        if not source_concept or not target_concept:
            continue

        # Check for existing relation
        existing_rel = await session.execute(
            select(ConceptRelation).where(
                ConceptRelation.source_concept_id == source_concept.id,
                ConceptRelation.target_concept_id == target_concept.id,
                ConceptRelation.relation_type == rel_data.relation_type,
            )
        )
        if existing_rel.scalar_one_or_none():
            continue

        relation = ConceptRelation(
            id=generate_id(),
            source_concept_id=source_concept.id,
            target_concept_id=target_concept.id,
            relation_type=rel_data.relation_type,
            confidence=rel_data.confidence,
            source_artifact_id=artifact_id,
        )
        session.add(relation)
        relation_count += 1

    await session.commit()

    logger.info(
        "concepts_extracted",
        artifact_id=artifact_id,
        concept_count=len(concept_map),
        relation_count=relation_count,
    )

    return {
        "concept_count": len(concept_map),
        "relation_count": relation_count,
    }


async def get_concepts(
    session: AsyncSession,
    user_id: str,
    course_id: str | None = None,
    search: str | None = None,
) -> list[dict]:
    """List concepts for a user, optionally filtered by course and search term.

    Args:
        session: Async DB session.
        user_id: Owner user ID.
        course_id: Optional course ID filter.
        search: Optional text search filter.

    Returns:
        List of concept dicts.
    """
    query = select(Concept).where(Concept.user_id == user_id)

    if course_id:
        query = query.where(Concept.course_id == course_id)

    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                Concept.name.ilike(search_pattern),
                Concept.description.ilike(search_pattern),
            )
        )

    query = query.order_by(Concept.mention_count.desc(), Concept.name)

    result = await session.execute(query)
    concepts = result.scalars().all()

    return [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "category": c.category,
            "mention_count": c.mention_count,
            "source_weeks": c.source_weeks or [],
            "course_id": c.course_id,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in concepts
    ]


async def get_concept_graph(
    session: AsyncSession,
    user_id: str,
    course_id: str | None = None,
) -> dict:
    """Build a knowledge graph (nodes + edges) for D3 visualization.

    Args:
        session: Async DB session.
        user_id: Owner user ID.
        course_id: Optional course ID filter.

    Returns:
        Dict with nodes and edges lists.
    """
    # Load concepts
    concept_query = select(Concept).where(Concept.user_id == user_id)
    if course_id:
        concept_query = concept_query.where(Concept.course_id == course_id)

    concept_result = await session.execute(concept_query)
    concepts = concept_result.scalars().all()

    concept_ids = {c.id for c in concepts}

    nodes = [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "category": c.category,
            "mention_count": c.mention_count,
            "source_weeks": c.source_weeks or [],
            "course_id": c.course_id,
        }
        for c in concepts
    ]

    # Load relations between these concepts
    if concept_ids:
        rel_query = select(ConceptRelation).where(
            ConceptRelation.source_concept_id.in_(concept_ids),
            ConceptRelation.target_concept_id.in_(concept_ids),
        )
        rel_result = await session.execute(rel_query)
        relations = rel_result.scalars().all()
    else:
        relations = []

    edges = [
        {
            "id": r.id,
            "source": r.source_concept_id,
            "target": r.target_concept_id,
            "relation_type": r.relation_type,
            "confidence": r.confidence,
        }
        for r in relations
    ]

    return {"nodes": nodes, "edges": edges}


async def get_concept_detail(
    session: AsyncSession,
    concept_id: str,
    user_id: str,
) -> dict | None:
    """Get detailed concept info with all relations.

    Args:
        session: Async DB session.
        concept_id: Concept UUID.
        user_id: Owner user ID.

    Returns:
        Concept detail dict or None.
    """
    result = await session.execute(
        select(Concept)
        .options(
            selectinload(Concept.outgoing_relations),
            selectinload(Concept.incoming_relations),
        )
        .where(Concept.id == concept_id, Concept.user_id == user_id)
    )
    concept = result.unique().scalar_one_or_none()

    if not concept:
        return None

    # Collect related concept IDs to fetch names
    related_ids = set()
    for r in concept.outgoing_relations:
        related_ids.add(r.target_concept_id)
    for r in concept.incoming_relations:
        related_ids.add(r.source_concept_id)

    related_names: dict[str, str] = {}
    if related_ids:
        names_result = await session.execute(
            select(Concept.id, Concept.name).where(Concept.id.in_(related_ids))
        )
        related_names = {row[0]: row[1] for row in names_result.all()}

    outgoing = [
        {
            "id": r.id,
            "target_id": r.target_concept_id,
            "target_name": related_names.get(r.target_concept_id, ""),
            "relation_type": r.relation_type,
            "confidence": r.confidence,
        }
        for r in concept.outgoing_relations
    ]

    incoming = [
        {
            "id": r.id,
            "source_id": r.source_concept_id,
            "source_name": related_names.get(r.source_concept_id, ""),
            "relation_type": r.relation_type,
            "confidence": r.confidence,
        }
        for r in concept.incoming_relations
    ]

    return {
        "id": concept.id,
        "name": concept.name,
        "description": concept.description,
        "category": concept.category,
        "mention_count": concept.mention_count,
        "source_artifact_ids": concept.source_artifact_ids or [],
        "source_weeks": concept.source_weeks or [],
        "course_id": concept.course_id,
        "outgoing_relations": outgoing,
        "incoming_relations": incoming,
        "created_at": concept.created_at.isoformat() if concept.created_at else None,
        "updated_at": concept.updated_at.isoformat() if concept.updated_at else None,
    }


async def find_related_concepts(
    session: AsyncSession,
    concept_id: str,
    user_id: str,
    limit: int = 10,
) -> list[dict]:
    """Find semantically similar concepts via pgvector.

    Args:
        session: Async DB session.
        concept_id: Concept UUID to find similar concepts for.
        user_id: Owner user ID.
        limit: Max results.

    Returns:
        List of similar concept dicts with similarity score.
    """
    # Get the source concept's embedding
    result = await session.execute(
        select(Concept).where(Concept.id == concept_id, Concept.user_id == user_id)
    )
    source = result.scalar_one_or_none()
    if not source or source.embedding is None:
        return []

    # Find similar concepts (cosine distance)
    similar_query = (
        select(
            Concept,
            Concept.embedding.cosine_distance(source.embedding).label("distance"),
        )
        .where(
            Concept.user_id == user_id,
            Concept.id != concept_id,
            Concept.embedding.isnot(None),
        )
        .order_by("distance")
        .limit(limit)
    )

    sim_result = await session.execute(similar_query)
    rows = sim_result.all()

    return [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "category": c.category,
            "course_id": c.course_id,
            "similarity": round(1.0 - dist, 3),
        }
        for c, dist in rows
        if dist < 0.5  # Only return reasonably similar concepts
    ]
