"""Contract test for `api.ai_feedback v1` (docs/CONTRACTS.md, M34-S3-BACKEND-012 note).

A ``v2`` adding a ``qa_answer`` target type was recorded and then withdrawn
before implementation (user decision, 2026-10-16): no UI calls
``POST /api/qa/ask``, so its answers are not rateable. The study-card half of
BACKEND-012 needs no backend change. Pins, all **green today**:

1. ``flashcard`` and ``quiz_question`` are target types, so the study surfaces
   can rate cards and questions with the card's or question's own id.
2. The target types are exactly the five v1 types, in order, and the service
   validates against the same tuple: no ``qa_answer``.
3. ``QAResponse`` carries no ``answer_id`` and there is no ``qa_answers`` table.
"""

from tests.contracts._weakspot_docs import contract_section

HEADING = "### api.ai_feedback v1"
V1_TYPES = ("summary", "answer", "flashcard", "quiz_question", "chat_message")


def test_entry_is_v1_and_records_the_withdrawal():
    section = contract_section(HEADING)
    assert "`qa_answer`" in section and "not** rateable" in section


def test_study_card_types_already_exist():
    from app.models.ai_feedback import AI_FEEDBACK_TARGET_TYPES

    assert {"flashcard", "quiz_question"} <= set(AI_FEEDBACK_TARGET_TYPES)


def test_target_types_are_the_five_v1_types():
    from app.models.ai_feedback import AI_FEEDBACK_TARGET_TYPES
    from app.services import ai_feedback_service

    assert AI_FEEDBACK_TARGET_TYPES == V1_TYPES
    assert ai_feedback_service.TARGET_TYPES == AI_FEEDBACK_TARGET_TYPES


def test_no_qa_answer_storage_or_id():
    import app.models  # noqa: F401  (registers every model on the metadata)
    from app.api.schemas import QAResponse
    from app.core.database import Base

    assert "qa_answers" not in Base.metadata.tables
    assert "answer_id" not in QAResponse.model_fields
