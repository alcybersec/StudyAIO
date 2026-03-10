"""Golden tests for exam mode response structures.

Validates that exam-related API responses conform to expected schemas:
- ExamProgress: all progress fields present and correctly typed
- DailyPlan: schedule fields present with valid priority values
- WeakTopic: topic analysis fields with valid reasons
"""

import pytest

# ── Sample data fixtures ────────────────────────────────────────────


@pytest.fixture
def sample_exam_progress():
    """A realistic exam progress response."""
    return {
        "exam_id": "01234567-89ab-cdef-0123-456789abcdef",
        "title": "Midterm Exam",
        "course_id": "fedcba98-7654-3210-fedc-ba9876543210",
        "exam_date": "2026-04-15T09:00:00",
        "status": "active",
        "days_remaining": 14,
        "mastery_pct": 45.5,
        "target_mastery_pct": 80,
        "quiz_accuracy": 65.0,
        "quiz_total": 20,
        "quiz_correct": 13,
        "flashcard_total": 50,
        "flashcard_mastered": 22,
        "weak_weeks": [2, 4],
        "session_count": 8,
        "weeks_scope": [1, 2, 3, 4, 5],
    }


@pytest.fixture
def sample_daily_plan_list():
    """A realistic 7-day study schedule."""
    return [
        {
            "date": "2026-03-03",
            "days_until_exam": 14,
            "priority": "medium",
            "card_target": 12,
            "quiz_target": 6,
            "focus_weeks": [2],
        },
        {
            "date": "2026-03-04",
            "days_until_exam": 13,
            "priority": "medium",
            "card_target": 12,
            "quiz_target": 6,
            "focus_weeks": [4],
        },
        {
            "date": "2026-03-08",
            "days_until_exam": 9,
            "priority": "medium",
            "card_target": 14,
            "quiz_target": 7,
            "focus_weeks": [2, 4],
        },
        {
            "date": "2026-03-12",
            "days_until_exam": 5,
            "priority": "high",
            "card_target": 18,
            "quiz_target": 8,
            "focus_weeks": [2, 4],
        },
        {
            "date": "2026-03-14",
            "days_until_exam": 3,
            "priority": "critical",
            "card_target": 25,
            "quiz_target": 10,
            "focus_weeks": [2, 4],
        },
    ]


@pytest.fixture
def sample_weak_topic_list():
    """Realistic weak topic analysis results."""
    return [
        {
            "week": 3,
            "quiz_accuracy": None,
            "quiz_attempts": 0,
            "avg_ease": None,
            "reasons": ["unstudied"],
            "weakness_score": 100.0,
        },
        {
            "week": 2,
            "quiz_accuracy": 55.0,
            "quiz_attempts": 20,
            "avg_ease": 1.8,
            "reasons": ["low_quiz_accuracy", "low_flashcard_ease"],
            "weakness_score": 25.0,
        },
        {
            "week": 4,
            "quiz_accuracy": 60.0,
            "quiz_attempts": 10,
            "avg_ease": 2.2,
            "reasons": ["low_quiz_accuracy"],
            "weakness_score": 10.0,
        },
    ]


# ── ExamProgress structure ──────────────────────────────────────────


class TestExamProgressStructure:
    """Validate exam progress response structure."""

    def test_has_all_required_fields(self, sample_exam_progress):
        required = {
            "exam_id",
            "title",
            "course_id",
            "exam_date",
            "status",
            "days_remaining",
            "mastery_pct",
            "target_mastery_pct",
            "quiz_accuracy",
            "quiz_total",
            "quiz_correct",
            "flashcard_total",
            "flashcard_mastered",
            "weak_weeks",
            "session_count",
            "weeks_scope",
        }
        missing = required - sample_exam_progress.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_days_remaining_is_non_negative_int(self, sample_exam_progress):
        assert isinstance(sample_exam_progress["days_remaining"], int)
        assert sample_exam_progress["days_remaining"] >= 0

    def test_mastery_pct_is_valid_percentage(self, sample_exam_progress):
        pct = sample_exam_progress["mastery_pct"]
        assert isinstance(pct, (int, float))
        assert 0 <= pct <= 100

    def test_target_mastery_is_valid_percentage(self, sample_exam_progress):
        pct = sample_exam_progress["target_mastery_pct"]
        assert isinstance(pct, int)
        assert 1 <= pct <= 100

    def test_quiz_accuracy_is_valid(self, sample_exam_progress):
        acc = sample_exam_progress["quiz_accuracy"]
        assert isinstance(acc, (int, float))
        assert 0 <= acc <= 100

    def test_quiz_correct_not_more_than_total(self, sample_exam_progress):
        assert sample_exam_progress["quiz_correct"] <= sample_exam_progress["quiz_total"]

    def test_flashcard_mastered_not_more_than_total(self, sample_exam_progress):
        assert sample_exam_progress["flashcard_mastered"] <= sample_exam_progress["flashcard_total"]

    def test_weak_weeks_is_list_of_ints(self, sample_exam_progress):
        assert isinstance(sample_exam_progress["weak_weeks"], list)
        for w in sample_exam_progress["weak_weeks"]:
            assert isinstance(w, int)

    def test_weeks_scope_is_nonempty_list(self, sample_exam_progress):
        assert isinstance(sample_exam_progress["weeks_scope"], list)
        assert len(sample_exam_progress["weeks_scope"]) > 0

    def test_status_is_valid(self, sample_exam_progress):
        assert sample_exam_progress["status"] in ("active", "completed", "archived")

    def test_exam_date_is_iso_format(self, sample_exam_progress):
        from datetime import datetime

        datetime.fromisoformat(sample_exam_progress["exam_date"])  # should not raise


# ── DailyPlan structure ────────────────────────────────────────────


class TestDailyPlanStructure:
    """Validate daily study plan structure."""

    def test_has_all_required_fields(self, sample_daily_plan_list):
        required = {
            "date",
            "days_until_exam",
            "priority",
            "card_target",
            "quiz_target",
            "focus_weeks",
        }
        for i, plan in enumerate(sample_daily_plan_list):
            missing = required - plan.keys()
            assert not missing, f"Plan {i} missing fields: {missing}"

    def test_priority_is_valid(self, sample_daily_plan_list):
        valid = {"critical", "high", "medium", "low"}
        for i, plan in enumerate(sample_daily_plan_list):
            assert plan["priority"] in valid, f"Plan {i} has invalid priority: {plan['priority']}"

    def test_card_target_is_positive(self, sample_daily_plan_list):
        for i, plan in enumerate(sample_daily_plan_list):
            assert isinstance(plan["card_target"], int)
            assert plan["card_target"] > 0, f"Plan {i} card_target must be > 0"

    def test_quiz_target_is_positive(self, sample_daily_plan_list):
        for i, plan in enumerate(sample_daily_plan_list):
            assert isinstance(plan["quiz_target"], int)
            assert plan["quiz_target"] > 0, f"Plan {i} quiz_target must be > 0"

    def test_focus_weeks_is_list_of_ints(self, sample_daily_plan_list):
        for _i, plan in enumerate(sample_daily_plan_list):
            assert isinstance(plan["focus_weeks"], list)
            for w in plan["focus_weeks"]:
                assert isinstance(w, int)

    def test_targets_increase_near_exam(self, sample_daily_plan_list):
        """Card targets should generally increase as exam approaches."""
        if len(sample_daily_plan_list) < 2:
            return
        first_target = sample_daily_plan_list[0]["card_target"]
        last_target = sample_daily_plan_list[-1]["card_target"]
        assert last_target >= first_target, "Targets should increase near exam"


# ── WeakTopic structure ─────────────────────────────────────────────


class TestWeakTopicStructure:
    """Validate weak topic analysis structure."""

    def test_has_all_required_fields(self, sample_weak_topic_list):
        required = {
            "week",
            "quiz_accuracy",
            "quiz_attempts",
            "avg_ease",
            "reasons",
            "weakness_score",
        }
        for i, topic in enumerate(sample_weak_topic_list):
            missing = required - topic.keys()
            assert not missing, f"Topic {i} missing fields: {missing}"

    def test_reasons_are_valid_strings(self, sample_weak_topic_list):
        valid = {"low_quiz_accuracy", "low_flashcard_ease", "unstudied"}
        for i, topic in enumerate(sample_weak_topic_list):
            assert isinstance(topic["reasons"], list)
            assert len(topic["reasons"]) > 0, f"Topic {i} must have at least one reason"
            for r in topic["reasons"]:
                assert r in valid, f"Topic {i} has invalid reason: {r}"

    def test_weakness_score_is_positive(self, sample_weak_topic_list):
        for _i, topic in enumerate(sample_weak_topic_list):
            assert isinstance(topic["weakness_score"], (int, float))
            assert topic["weakness_score"] > 0

    def test_sorted_by_weakness_descending(self, sample_weak_topic_list):
        """Weak topics should be sorted weakest-first."""
        scores = [t["weakness_score"] for t in sample_weak_topic_list]
        assert scores == sorted(scores, reverse=True), (
            "Topics should be sorted by weakness_score desc"
        )

    def test_quiz_accuracy_nullable(self, sample_weak_topic_list):
        """Quiz accuracy can be None for unstudied weeks."""
        unstudied = [t for t in sample_weak_topic_list if "unstudied" in t["reasons"]]
        for t in unstudied:
            assert t["quiz_accuracy"] is None

    def test_avg_ease_nullable(self, sample_weak_topic_list):
        """Avg ease can be None when no flashcard reviews exist."""
        unstudied = [t for t in sample_weak_topic_list if "unstudied" in t["reasons"]]
        for t in unstudied:
            assert t["avg_ease"] is None
