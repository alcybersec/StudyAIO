"""SQLAlchemy ORM models.

Import all models here so Alembic's autogenerate can discover them.
"""

from app.models.course import Course
from app.models.artifact import LectureArtifact
from app.models.extraction import Extraction
from app.models.summary import Summary
from app.models.chunk import Chunk
from app.models.flashcard import Flashcard
from app.models.quiz import QuizQuestion
from app.models.review_item import ReviewItem
from app.models.pipeline_run import PipelineRun

__all__ = [
    "Course",
    "LectureArtifact",
    "Extraction",
    "Summary",
    "Chunk",
    "Flashcard",
    "QuizQuestion",
    "ReviewItem",
    "PipelineRun",
]
