"""SQLAlchemy ORM models.

Import all models here so Alembic's autogenerate can discover them.
"""

from app.models.artifact import LectureArtifact
from app.models.assessment import Assessment
from app.models.chunk import Chunk
from app.models.course import Course
from app.models.course_document import CourseDocument
from app.models.deadline import Deadline
from app.models.exam import Exam
from app.models.extraction import Extraction
from app.models.flashcard import Flashcard
from app.models.flashcard_review import FlashcardReview
from app.models.pipeline_run import PipelineRun
from app.models.quiz import QuizQuestion
from app.models.quiz_attempt import QuizAttempt
from app.models.review_item import ReviewItem
from app.models.study_session import StudySession
from app.models.summary import Summary

__all__ = [
    "Assessment",
    "Course",
    "CourseDocument",
    "Deadline",
    "Exam",
    "LectureArtifact",
    "Extraction",
    "Summary",
    "Chunk",
    "Flashcard",
    "FlashcardReview",
    "QuizQuestion",
    "QuizAttempt",
    "ReviewItem",
    "StudySession",
    "PipelineRun",
]
