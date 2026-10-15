"""Weak-spot storage models (ADR 0007 Decision 6): defaults and index names."""

from app.models import Flashcard, QuizAttempt, QuizQuestion, StudyPlan, TargetedGeneration


def test_new_tables_have_indexed_user_id():
    plan_idx = {tuple(c.name for c in ix.columns) for ix in StudyPlan.__table__.indexes}
    gen_idx = {tuple(c.name for c in ix.columns) for ix in TargetedGeneration.__table__.indexes}
    assert ("user_id",) in plan_idx
    assert ("user_id", "created_at") in gen_idx


def test_in_flight_index_is_partial_unique_on_status():
    ix = next(
        i
        for i in TargetedGeneration.__table__.indexes
        if i.name == "uq_targeted_generations_in_flight"
    )
    assert ix.unique
    assert [c.name for c in ix.columns] == ["user_id", "course_id", "week", "kind"]
    where = str(ix.dialect_options["postgresql"]["where"])
    assert "queued" in where and "running" in where
    assert "completed" not in where and "failed" not in where


def test_item_provenance_columns_default_to_pipeline():
    for model in (QuizQuestion, Flashcard):
        cols = model.__table__.columns
        assert cols["origin"].nullable is False
        assert str(cols["origin"].server_default.arg) == "pipeline"
        assert cols["targeted_generation_id"].nullable is True
        assert cols["focus_topic"].nullable is True


def test_attempts_scoring_index_name():
    names = {i.name for i in QuizAttempt.__table__.indexes}
    assert "ix_quiz_attempts_question_created" in names
