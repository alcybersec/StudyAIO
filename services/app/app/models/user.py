"""User model."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import generate_id


class User(Base):
    """Application user with authentication and profile data."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="free")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    backup_codes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships — auth
    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    magic_links: Mapped[list["MagicLink"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    # Relationships — data ownership
    courses: Mapped[list["Course"]] = relationship(back_populates="user")
    artifacts: Mapped[list["LectureArtifact"]] = relationship(back_populates="user")
    exams: Mapped[list["Exam"]] = relationship(back_populates="user")
    study_sessions: Mapped[list["StudySession"]] = relationship(back_populates="user")
    flashcard_reviews: Mapped[list["FlashcardReview"]] = relationship(back_populates="user")
    course_documents: Mapped[list["CourseDocument"]] = relationship(back_populates="user")
    settings: Mapped["UserSettings | None"] = relationship(back_populates="user", uselist=False)

    # Relationships — gamification
    user_xp: Mapped["UserXP | None"] = relationship(uselist=False)
    xp_events: Mapped[list["XPEvent"]] = relationship()
    user_achievements: Mapped[list["UserAchievement"]] = relationship()

    __table_args__ = (
        Index("ix_users_email", "email", unique=True),
        Index("ix_users_username", "username", unique=True),
        Index("ix_users_role", "role"),
    )
