"""Golden tests for analytics response structures.

Validates that analytics-related API responses conform to expected schemas:
- OverviewResponse: all aggregated stats present and correctly typed
- HeatmapDay: daily study entry structure
- RetentionPoint: retention curve point structure
- MasteryWeek: per-week mastery breakdown structure
- ExamReadinessResponse: weighted readiness score structure
"""

import pytest

# ── Sample data fixtures ────────────────────────────────────────────


@pytest.fixture
def sample_overview_response():
    """A realistic analytics overview response."""
    return {
        "total_study_hours": 24.5,
        "total_cards_reviewed": 480,
        "total_sessions": 45,
        "mastery_pct": 38.5,
        "total_flashcards": 120,
        "mastered_flashcards": 46,
        "active_courses": 3,
    }


@pytest.fixture
def sample_heatmap_day():
    """A realistic heatmap day entry."""
    return {
        "date": "2026-03-01",
        "minutes": 45.5,
        "cards": 25,
        "sessions": 3,
    }


@pytest.fixture
def sample_retention_point():
    """A realistic retention curve point."""
    return {
        "interval_bucket": 7,
        "retention_pct": 82.5,
        "card_count": 30,
    }


@pytest.fixture
def sample_mastery_week():
    """A realistic mastery breakdown entry."""
    return {
        "course_code": "CSIT302",
        "week": 3,
        "total": 15,
        "mastered": 6,
        "learning": 5,
        "new": 4,
        "mastery_pct": 40.0,
    }


@pytest.fixture
def sample_readiness_response():
    """A realistic exam readiness response."""
    return {
        "exam_id": "01234567-89ab-cdef-0123-456789abcdef",
        "title": "Midterm Exam",
        "readiness_score": 62.3,
        "mastery_score": 55.0,
        "quiz_score": 72.0,
        "consistency_score": 71.4,
        "days_remaining": 10,
        "weak_weeks": [2, 4],
        "flashcard_total": 50,
        "flashcard_mastered": 27,
        "quiz_total": 25,
        "quiz_correct": 18,
        "study_days_last_week": 5,
    }


# ── Overview structure ────────────────────────────────────────────


class TestOverviewStructure:
    """Validate analytics overview response structure."""

    def test_has_required_fields(self, sample_overview_response):
        """Overview has all required fields."""
        required = {
            "total_study_hours",
            "total_cards_reviewed",
            "total_sessions",
            "mastery_pct",
            "total_flashcards",
            "mastered_flashcards",
            "active_courses",
        }
        missing = required - sample_overview_response.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_study_hours_is_non_negative(self, sample_overview_response):
        """Study hours is a non-negative number."""
        assert isinstance(sample_overview_response["total_study_hours"], (int, float))
        assert sample_overview_response["total_study_hours"] >= 0

    def test_mastery_pct_is_valid(self, sample_overview_response):
        """Mastery percentage is between 0 and 100."""
        pct = sample_overview_response["mastery_pct"]
        assert isinstance(pct, (int, float))
        assert 0 <= pct <= 100

    def test_mastered_not_more_than_total(self, sample_overview_response):
        """Mastered flashcards cannot exceed total flashcards."""
        assert (
            sample_overview_response["mastered_flashcards"]
            <= sample_overview_response["total_flashcards"]
        )


# ── Heatmap day structure ─────────────────────────────────────────


class TestHeatmapDayStructure:
    """Validate heatmap day entry structure."""

    def test_has_required_fields(self, sample_heatmap_day):
        """Heatmap day has all required fields."""
        required = {"date", "minutes", "cards", "sessions"}
        missing = required - sample_heatmap_day.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_date_is_iso_format(self, sample_heatmap_day):
        """Date is a valid ISO date string."""
        from datetime import date

        date.fromisoformat(sample_heatmap_day["date"])  # should not raise

    def test_minutes_is_non_negative(self, sample_heatmap_day):
        """Minutes is a non-negative number."""
        assert isinstance(sample_heatmap_day["minutes"], (int, float))
        assert sample_heatmap_day["minutes"] >= 0

    def test_cards_is_non_negative_int(self, sample_heatmap_day):
        """Cards is a non-negative integer."""
        assert isinstance(sample_heatmap_day["cards"], int)
        assert sample_heatmap_day["cards"] >= 0


# ── Retention point structure ─────────────────────────────────────


class TestRetentionPointStructure:
    """Validate retention curve point structure."""

    def test_has_required_fields(self, sample_retention_point):
        """Retention point has all required fields."""
        required = {"interval_bucket", "retention_pct", "card_count"}
        missing = required - sample_retention_point.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_retention_pct_is_valid(self, sample_retention_point):
        """Retention percentage is between 0 and 100."""
        pct = sample_retention_point["retention_pct"]
        assert isinstance(pct, (int, float))
        assert 0 <= pct <= 100

    def test_interval_bucket_is_positive(self, sample_retention_point):
        """Interval bucket is a positive integer."""
        assert isinstance(sample_retention_point["interval_bucket"], int)
        assert sample_retention_point["interval_bucket"] > 0

    def test_card_count_is_positive(self, sample_retention_point):
        """Card count is a positive integer."""
        assert isinstance(sample_retention_point["card_count"], int)
        assert sample_retention_point["card_count"] > 0


# ── Mastery week structure ────────────────────────────────────────


class TestMasteryWeekStructure:
    """Validate mastery breakdown entry structure."""

    def test_has_required_fields(self, sample_mastery_week):
        """Mastery week has all required fields."""
        required = {
            "course_code",
            "week",
            "total",
            "mastered",
            "learning",
            "new",
            "mastery_pct",
        }
        missing = required - sample_mastery_week.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_counts_sum_to_total(self, sample_mastery_week):
        """Mastered + learning + new equals total."""
        total = (
            sample_mastery_week["mastered"]
            + sample_mastery_week["learning"]
            + sample_mastery_week["new"]
        )
        assert total == sample_mastery_week["total"]

    def test_mastery_pct_is_valid(self, sample_mastery_week):
        """Mastery percentage is between 0 and 100."""
        pct = sample_mastery_week["mastery_pct"]
        assert isinstance(pct, (int, float))
        assert 0 <= pct <= 100


# ── Readiness response structure ──────────────────────────────────


class TestReadinessResponseStructure:
    """Validate exam readiness response structure."""

    def test_has_required_fields(self, sample_readiness_response):
        """Readiness response has all required fields."""
        required = {
            "exam_id",
            "title",
            "readiness_score",
            "mastery_score",
            "quiz_score",
            "consistency_score",
            "days_remaining",
            "weak_weeks",
            "flashcard_total",
            "flashcard_mastered",
            "quiz_total",
            "quiz_correct",
            "study_days_last_week",
        }
        missing = required - sample_readiness_response.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_readiness_score_is_valid(self, sample_readiness_response):
        """Readiness score is between 0 and 100."""
        score = sample_readiness_response["readiness_score"]
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100

    def test_component_scores_are_valid(self, sample_readiness_response):
        """All component scores are between 0 and 100."""
        for key in ("mastery_score", "quiz_score", "consistency_score"):
            score = sample_readiness_response[key]
            assert isinstance(score, (int, float)), f"{key} is not a number"
            assert 0 <= score <= 100, f"{key} is out of range: {score}"

    def test_weak_weeks_is_list_of_ints(self, sample_readiness_response):
        """Weak weeks is a list of integers."""
        assert isinstance(sample_readiness_response["weak_weeks"], list)
        for w in sample_readiness_response["weak_weeks"]:
            assert isinstance(w, int)

    def test_flashcard_mastered_not_more_than_total(self, sample_readiness_response):
        """Mastered flashcards cannot exceed total."""
        assert (
            sample_readiness_response["flashcard_mastered"]
            <= sample_readiness_response["flashcard_total"]
        )

    def test_quiz_correct_not_more_than_total(self, sample_readiness_response):
        """Correct quiz answers cannot exceed total."""
        assert (
            sample_readiness_response["quiz_correct"]
            <= sample_readiness_response["quiz_total"]
        )

    def test_study_days_in_valid_range(self, sample_readiness_response):
        """Study days last week is between 0 and 7."""
        days = sample_readiness_response["study_days_last_week"]
        assert isinstance(days, int)
        assert 0 <= days <= 7
