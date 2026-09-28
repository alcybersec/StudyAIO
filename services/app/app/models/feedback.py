"""Feedback submitted from inside the app."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id

#: What the reporter says this is. Deliberately three, not a taxonomy: a list
#: long enough to need thought is a list people pick the first item from.
FEEDBACK_KINDS = ("bug", "idea", "confusing")

#: Triage state. `new` until someone looks at it.
FEEDBACK_STATUSES = ("new", "triaged", "closed")


class Feedback(Base):
    """One piece of feedback from a user.

    Sentry records what crashed. This records what a person found wrong,
    missing or confusing, which no amount of instrumentation infers — the beta
    funnel can show that someone stopped after their first upload, never why.

    `route` and `app_version` exist so a report can be tied to a place and a
    build. Without them "the summary looked empty" is unactionable; with them it
    is a page and a commit.

    **Deleted with the account.** `user_id` is a non-nullable FK, so this table
    is user-scoped and `account_service.delete_user_account` removes it along
    with everything else the user owns. That loses the signal when a tester
    leaves, which is a real cost — but the message is free text the user wrote
    and may name them or anyone else, and "delete my account" has to mean it.
    Anonymising by nulling `user_id` would keep the text, which is the part that
    carries the risk.
    """

    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="bug")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    #: The route the reporter was on, e.g. `/courses/CSIT302/weeks/3`.
    route: Mapped[str | None] = mapped_column(String(500), nullable=True)
    #: Commit SHA of the build they were running, so a fixed bug can be told
    #: apart from one still live.
    app_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="new")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    user: Mapped["User"] = relationship()  # noqa: F821

    __table_args__ = (
        Index("ix_feedback_user_id", "user_id"),
        # The admin inbox reads newest-first, filtered by status.
        Index("ix_feedback_status_created", "status", "created_at"),
    )
