"""SQLAlchemy ORM models.

Import all models here so Alembic's autogenerate can discover them.
"""

from app.models.achievement import Achievement
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.models.artifact import LectureArtifact
from app.models.assessment import Assessment
from app.models.calendar_event import CalendarEvent
from app.models.calendar_sync import CalendarSync
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.chunk import Chunk
from app.models.concept import Concept
from app.models.concept_relation import ConceptRelation
from app.models.course import Course
from app.models.course_document import CourseDocument
from app.models.daily_challenge import DailyChallenge
from app.models.deadline import Deadline
from app.models.exam import Exam
from app.models.extraction import Extraction
from app.models.flashcard import Flashcard
from app.models.flashcard_review import FlashcardReview
from app.models.magic_link import MagicLink
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.models.oauth_account import OAuthAccount
from app.models.pipeline_run import PipelineRun
from app.models.push_subscription import PushSubscription
from app.models.quiz import QuizQuestion
from app.models.quiz_attempt import QuizAttempt
from app.models.review_item import ReviewItem
from app.models.study_session import StudySession
from app.models.subscription import Subscription
from app.models.summary import Summary
from app.models.telegram_link import TelegramLink
from app.models.usage_record import UsageRecord
from app.models.user import User
from app.models.user_achievement import UserAchievement
from app.models.user_daily_challenge import UserDailyChallenge
from app.models.user_settings import UserSettings
from app.models.user_xp import UserXP
from app.models.xp_event import XPEvent

__all__ = [
    "Achievement",
    "AnalyticsSnapshot",
    "CalendarEvent",
    "CalendarSync",
    "Concept",
    "ConceptRelation",
    "Assessment",
    "ChatMessage",
    "ChatSession",
    "Chunk",
    "Course",
    "CourseDocument",
    "DailyChallenge",
    "Deadline",
    "Exam",
    "Extraction",
    "Flashcard",
    "FlashcardReview",
    "LectureArtifact",
    "MagicLink",
    "Notification",
    "NotificationPreference",
    "OAuthAccount",
    "PipelineRun",
    "PushSubscription",
    "QuizAttempt",
    "QuizQuestion",
    "ReviewItem",
    "StudySession",
    "Subscription",
    "Summary",
    "TelegramLink",
    "UsageRecord",
    "User",
    "UserAchievement",
    "UserDailyChallenge",
    "UserSettings",
    "UserXP",
    "XPEvent",
]
