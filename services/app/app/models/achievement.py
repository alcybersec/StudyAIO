"""Achievement model — defines available achievements."""

from datetime import datetime

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.utils import generate_id


class Achievement(Base):
    """Defines an achievement with criteria for unlocking."""

    __tablename__ = "achievements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    icon: Mapped[str] = mapped_column(String(50), nullable=False, default="star")
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="milestone")
    xp_reward: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    criteria_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
