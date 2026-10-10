"""SummaryVersion model — immutable history of superseded summaries."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.utils import generate_id


class SummaryVersion(Base):
    """A prior version of a course-week summary, kept when it is superseded.

    ``summaries`` always holds the *current* version. Before a re-summarize
    replaces that row, the service snapshots it here (floor 4: a re-summarize
    never destroys a prior version). Rows are append-only: never updated, never
    deleted except by account or course deletion.

    ``file_path`` is the blob key the version was written to. Every version is
    written to its own key (see ``summary_service``), so that blob is still
    intact. A snapshot of a pre-versioning summary points at the legacy
    unversioned ``Week<N>.md`` key, which re-summarize must no longer overwrite.
    """

    __tablename__ = "summary_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(String(36), ForeignKey("courses.id"), nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_artifacts: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    #: When this version was generated (the source row's updated_at at snapshot time).
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint(
            "course_id", "week", "version", name="uq_summary_versions_course_week_ver"
        ),
        Index("ix_summary_versions_user_id", "user_id"),
        Index("ix_summary_versions_course_week", "course_id", "week"),
    )
