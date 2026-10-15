"""Request schemas for user-authored flashcards and quiz questions (GL#48)."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

TEXT_MAX = 4000


class _Text(BaseModel):
    """Strips whitespace on the text fields and rejects blank ones."""

    @field_validator(
        "front", "back", "question", "correct_answer", mode="after", check_fields=False
    )
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class FlashcardCreate(_Text):
    """Manual flashcard for a course and week."""

    course_code: str = Field(min_length=1, max_length=20)
    week: int = Field(ge=1, le=52)
    front: str = Field(min_length=1, max_length=TEXT_MAX)
    back: str = Field(min_length=1, max_length=TEXT_MAX)
    tags: list[str] = Field(default_factory=list, max_length=20)
    source_artifact_id: str | None = Field(default=None, max_length=36)


class FlashcardUpdate(_Text):
    """Edit of a flashcard; at least one field."""

    front: str | None = Field(default=None, min_length=1, max_length=TEXT_MAX)
    back: str | None = Field(default=None, min_length=1, max_length=TEXT_MAX)
    tags: list[str] | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def _non_empty(self) -> "FlashcardUpdate":
        if not self.model_fields_set & {"front", "back", "tags"}:
            raise ValueError("provide at least one of front, back, tags")
        return self


class QuizQuestionCreate(_Text):
    """Manual quiz question for a course and week."""

    course_code: str = Field(min_length=1, max_length=20)
    week: int = Field(ge=1, le=52)
    question_type: Literal["multiple_choice", "short_answer"]
    question: str = Field(min_length=1, max_length=TEXT_MAX)
    options: list[str] | None = Field(default=None, max_length=8)
    correct_answer: str = Field(min_length=1, max_length=TEXT_MAX)
    explanation: str = Field(default="", max_length=TEXT_MAX)
    source_artifact_id: str | None = Field(default=None, max_length=36)
    # Type/options/answer coherence is checked by asset_service.validate_quiz_shape
    # (the endpoint maps its ValueError to 422), so it holds for every caller.


class QuizQuestionUpdate(_Text):
    """Edit of a quiz question; at least one field. Coherence is checked against the original."""

    question: str | None = Field(default=None, min_length=1, max_length=TEXT_MAX)
    options: list[str] | None = Field(default=None, max_length=8)
    correct_answer: str | None = Field(default=None, min_length=1, max_length=TEXT_MAX)
    explanation: str | None = Field(default=None, max_length=TEXT_MAX)

    @model_validator(mode="after")
    def _non_empty(self) -> "QuizQuestionUpdate":
        if not self.model_fields_set & {"question", "options", "correct_answer", "explanation"}:
            raise ValueError("provide at least one field")
        return self
