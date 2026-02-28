"""AI agent adapters."""

from app.agents.base import (
    AgentAdapter,
    AnswerResult,
    ClassificationResult,
    ExtractionData,
    FlashcardData,
    QuizQuestionData,
    SummaryResult,
)
from app.agents.factory import get_agent

__all__ = [
    "AgentAdapter",
    "AnswerResult",
    "ClassificationResult",
    "ExtractionData",
    "FlashcardData",
    "QuizQuestionData",
    "SummaryResult",
    "get_agent",
]
