"""Per-item thumbs up/down on AI output (M33-S1-BACKEND-015, GL#36).

The database enforces none of the value rules, so this module does: target
type, rating, reason and comment length are validated here, and the target must
exist **and belong to the caller** before a vote is stored (floor 1). A target
that is missing and one owned by someone else are indistinguishable to the
caller, so the endpoint cannot be used to probe for another user's ids.

This is distinct from `feedback_service`, which handles bug/idea reports about
the app itself.
"""

from datetime import timedelta

import structlog
from prometheus_client import Counter
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.models.ai_feedback import AI_FEEDBACK_REASONS, AI_FEEDBACK_TARGET_TYPES, AIFeedback
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.services import exam_service, srs_service, summary_service

logger = structlog.get_logger()

TARGET_TYPES = AI_FEEDBACK_TARGET_TYPES
REASONS = AI_FEEDBACK_REASONS
MAX_COMMENT_LENGTH = 1000
#: Most negative comments the admin aggregate returns.
RECENT_NEGATIVE_LIMIT = 50

# The label is a fixed enum (up | down); never an id or free text.
AI_FEEDBACK_VOTES = Counter(
    "studyaio_ai_feedback_votes_total",
    "AI feedback votes stored, by direction.",
    ["outcome"],
)


class FeedbackTargetNotFoundError(LookupError):
    """The target does not exist or is not the caller's (deliberately the same)."""


def _validate_target_type(target_type: str) -> None:
    if target_type not in TARGET_TYPES:
        raise ValueError(f"target_type must be one of: {', '.join(TARGET_TYPES)}")


def _validate(target_type: str, rating: int, reason: str | None, comment: str | None) -> None:
    _validate_target_type(target_type)
    if isinstance(rating, bool) or rating not in (1, -1):
        raise ValueError("rating must be 1 or -1")
    if reason is not None:
        if reason not in REASONS:
            raise ValueError(f"reason must be one of: {', '.join(REASONS)}")
        if rating != -1:
            raise ValueError("reason is only allowed with a thumbs-down (rating -1)")
    if comment is not None and len(comment) > MAX_COMMENT_LENGTH:
        raise ValueError(f"comment must be at most {MAX_COMMENT_LENGTH} characters")


async def _owned_chat_course(
    session: AsyncSession, message_id: str, user_id: str, *, assistant_only: bool
) -> tuple[bool, str | None]:
    """Whether the caller owns this chat message, and the course of its session."""
    stmt = (
        select(ChatSession)
        .join(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .where(ChatMessage.id == message_id, ChatSession.user_id == user_id)
    )
    if assistant_only:
        stmt = stmt.where(ChatMessage.role == "assistant")
    chat_session = (await session.execute(stmt)).scalar_one_or_none()
    if chat_session is None:
        return False, None
    return True, chat_session.course_id


async def resolve_target_course(
    session: AsyncSession, user_id: str, target_type: str, target_id: str
) -> str | None:
    """Check the target belongs to the caller and return its course id.

    Args:
        session: Database session.
        user_id: The caller.
        target_type: One of `TARGET_TYPES`.
        target_id: Caller-supplied id.

    Returns:
        The target's course id (None for a chat message outside any course).

    Raises:
        FeedbackTargetNotFoundError: Missing or owned by someone else.
    """
    if target_type in ("answer", "chat_message"):
        found, course_id = await _owned_chat_course(
            session, target_id, user_id, assistant_only=target_type == "answer"
        )
        if not found:
            raise FeedbackTargetNotFoundError(target_type)
        return course_id

    if target_type == "summary":
        target = await summary_service.get_summary_by_id(session, target_id, user_id=user_id)
    elif target_type == "flashcard":
        target = await srs_service.get_owned_flashcard(session, target_id, user_id=user_id)
    else:
        target = await exam_service.get_owned_quiz_question(session, target_id, user_id=user_id)
    if target is None:
        raise FeedbackTargetNotFoundError(target_type)
    return target.course_id


async def upsert_vote(
    session: AsyncSession,
    *,
    user_id: str,
    target_type: str,
    target_id: str,
    rating: int,
    reason: str | None = None,
    comment: str | None = None,
) -> AIFeedback:
    """Store the caller's vote on a target, replacing any earlier one.

    The caller commits.

    Raises:
        ValueError: A value rule failed.
        FeedbackTargetNotFoundError: Target missing or not the caller's.
    """
    comment = comment.strip() or None if comment is not None else None
    _validate(target_type, rating, reason, comment)
    course_id = await resolve_target_course(session, user_id, target_type, target_id)

    existing = (
        await session.execute(
            select(AIFeedback).where(
                AIFeedback.user_id == user_id,
                AIFeedback.target_type == target_type,
                AIFeedback.target_id == target_id,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        vote = existing
        vote.rating, vote.reason, vote.comment, vote.course_id = rating, reason, comment, course_id
    else:
        vote = AIFeedback(
            user_id=user_id,
            target_type=target_type,
            target_id=target_id,
            rating=rating,
            reason=reason,
            comment=comment,
            course_id=course_id,
        )
        session.add(vote)
    await session.flush()

    if rating == 1:
        AI_FEEDBACK_VOTES.labels(outcome="up").inc()
    else:
        AI_FEEDBACK_VOTES.labels(outcome="down").inc()
    logger.info(
        "ai_feedback_recorded",
        user_id=user_id,
        target_type=target_type,
        rating=rating,
        reason=reason,
        replaced=existing is not None,
    )
    return vote


async def delete_vote(
    session: AsyncSession, *, user_id: str, target_type: str, target_id: str
) -> bool:
    """Remove the caller's own vote. Returns whether one existed. Caller commits."""
    _validate_target_type(target_type)
    result = await session.execute(
        delete(AIFeedback).where(
            AIFeedback.user_id == user_id,
            AIFeedback.target_type == target_type,
            AIFeedback.target_id == target_id,
        )
    )
    return bool(result.rowcount)


async def list_votes(
    session: AsyncSession, *, user_id: str, target_type: str, target_ids: list[str]
) -> list[AIFeedback]:
    """The caller's votes on the given targets (so the UI can show state)."""
    _validate_target_type(target_type)
    if not target_ids:
        return []
    result = await session.execute(
        select(AIFeedback).where(
            AIFeedback.user_id == user_id,
            AIFeedback.target_type == target_type,
            AIFeedback.target_id.in_(target_ids),
        )
    )
    return list(result.scalars().all())


def build_admin_summary(
    by_target: list[tuple[str, int, int]],
    by_reason: list[tuple[str, int]],
    recent: list[dict],
) -> dict:
    """Assemble the admin payload from aggregate rows (no user identifiers)."""
    per_type: dict[str, dict[str, int]] = {}
    up = down = 0
    for target_type, rating, count in by_target:
        bucket = per_type.setdefault(target_type, {"up": 0, "down": 0})
        if rating == 1:
            bucket["up"] += count
            up += count
        else:
            bucket["down"] += count
            down += count
    return {
        "total": up + down,
        "by_target_type": per_type,
        "by_reason": {reason: count for reason, count in by_reason},
        "by_rating": {"up": up, "down": down},
        "recent_negative": recent,
    }


async def admin_summary(session: AsyncSession, *, days: int = 30) -> dict:
    """Counts per target type / rating / reason, and recent thumbs-down comments.

    Cross-user by design (admin only); returns no user ids or emails.
    """
    since = utc_now() - timedelta(days=days)
    by_target = (
        await session.execute(
            select(AIFeedback.target_type, AIFeedback.rating, func.count())
            .where(AIFeedback.updated_at >= since)
            .group_by(AIFeedback.target_type, AIFeedback.rating)
        )
    ).all()
    by_reason = (
        await session.execute(
            select(AIFeedback.reason, func.count())
            .where(AIFeedback.updated_at >= since, AIFeedback.rating == -1)
            .where(AIFeedback.reason.is_not(None))
            .group_by(AIFeedback.reason)
        )
    ).all()
    rows = (
        (
            await session.execute(
                select(AIFeedback)
                .where(
                    AIFeedback.updated_at >= since,
                    AIFeedback.rating == -1,
                    AIFeedback.comment.is_not(None),
                )
                .order_by(AIFeedback.updated_at.desc())
                .limit(RECENT_NEGATIVE_LIMIT)
            )
        )
        .scalars()
        .all()
    )
    recent = [
        {
            "target_type": r.target_type,
            "reason": r.reason,
            "comment": r.comment,
            "course_id": r.course_id,
            "created_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]
    return build_admin_summary(
        [(t, r, c) for t, r, c in by_target], [(r, c) for r, c in by_reason], recent
    )
