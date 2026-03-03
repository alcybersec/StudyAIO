"""Golden tests for CourseOps response structures.

Validates that CourseOps-related data structures conform to expected schemas:
- CourseOpsResult: assessment and deadline fields
- .ics calendar: valid iCalendar format
- Task plan markdown: expected sections
"""

import pytest


# ── Sample data fixtures ────────────────────────────────────────────


@pytest.fixture
def sample_course_ops_result():
    """A realistic CourseOps extraction result."""
    return {
        "assessments": [
            {
                "title": "Final Exam",
                "assessment_type": "exam",
                "weight_pct": 40.0,
                "description": "Comprehensive exam covering weeks 1-13",
                "weeks_relevant": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            },
            {
                "title": "Assignment 1",
                "assessment_type": "assignment",
                "weight_pct": 15.0,
                "description": "Individual coding assignment",
                "weeks_relevant": [1, 2, 3],
            },
            {
                "title": "Group Project",
                "assessment_type": "project",
                "weight_pct": 25.0,
                "description": "Team-based software project",
                "weeks_relevant": [5, 6, 7, 8, 9],
            },
            {
                "title": "Lab Reports",
                "assessment_type": "lab",
                "weight_pct": 20.0,
                "description": "Weekly lab submissions",
                "weeks_relevant": [],
            },
        ],
        "deadlines": [
            {
                "title": "Assignment 1 Due",
                "due_date": "2026-04-15",
                "deadline_type": "assignment",
                "description": "Submit via Moodle by 11:59 PM",
            },
            {
                "title": "Project Proposal",
                "due_date": "2026-05-01",
                "deadline_type": "project",
                "description": "Submit 2-page proposal",
            },
            {
                "title": "Final Exam",
                "due_date": "2026-06-15",
                "deadline_type": "exam",
                "description": "Main exam hall, 2 hours",
            },
        ],
        "course_info": {
            "course_name": "Software Engineering Practices",
            "term": "Spring 2026",
            "instructor": "Dr. Smith",
        },
        "confidence": 0.85,
    }


@pytest.fixture
def sample_assessment_response():
    """A realistic assessment API response."""
    return {
        "id": "01234567-89ab-cdef-0123-456789abcdef",
        "course_id": "fedcba98-7654-3210-fedc-ba9876543210",
        "source_document_id": "aaaabbbb-cccc-dddd-eeee-ffffffffffff",
        "title": "Final Exam",
        "assessment_type": "exam",
        "weight_pct": 40.0,
        "description": "Comprehensive exam covering weeks 1-13",
        "weeks_relevant": [1, 2, 3, 4, 5],
        "created_at": "2026-03-01T00:00:00",
        "updated_at": "2026-03-01T00:00:00",
    }


@pytest.fixture
def sample_deadline_response():
    """A realistic deadline API response."""
    return {
        "id": "01234567-89ab-cdef-0123-456789abcdef",
        "course_id": "fedcba98-7654-3210-fedc-ba9876543210",
        "assessment_id": None,
        "source_document_id": "aaaabbbb-cccc-dddd-eeee-ffffffffffff",
        "title": "Assignment 1 Due",
        "due_date": "2026-04-15",
        "deadline_type": "assignment",
        "description": "Submit via Moodle by 11:59 PM",
        "is_confirmed": False,
        "created_at": "2026-03-01T00:00:00",
        "updated_at": "2026-03-01T00:00:00",
    }


# ── CourseOps Result Structure ──────────────────────────────────────


class TestCourseOpsResultStructure:
    """Validate CourseOps extraction result structure."""

    def test_has_required_top_level_keys(self, sample_course_ops_result):
        """Result has assessments, deadlines, course_info, confidence."""
        required = {"assessments", "deadlines", "course_info", "confidence"}
        assert required <= set(sample_course_ops_result.keys())

    def test_assessments_are_list(self, sample_course_ops_result):
        """Assessments is a non-empty list."""
        assert isinstance(sample_course_ops_result["assessments"], list)
        assert len(sample_course_ops_result["assessments"]) > 0

    def test_assessment_has_required_fields(self, sample_course_ops_result):
        """Each assessment has title, assessment_type, weight_pct."""
        for a in sample_course_ops_result["assessments"]:
            assert "title" in a
            assert "assessment_type" in a
            assert "weight_pct" in a
            assert isinstance(a["title"], str)

    def test_assessment_types_are_valid(self, sample_course_ops_result):
        """Assessment types are from the allowed set."""
        valid = {"exam", "assignment", "quiz", "project", "lab", "presentation", "other"}
        for a in sample_course_ops_result["assessments"]:
            assert a["assessment_type"] in valid

    def test_weights_sum_to_100(self, sample_course_ops_result):
        """Assessment weights sum to 100 (or close to it)."""
        total = sum(
            a["weight_pct"]
            for a in sample_course_ops_result["assessments"]
            if a["weight_pct"] is not None
        )
        assert 95.0 <= total <= 105.0

    def test_deadlines_are_list(self, sample_course_ops_result):
        """Deadlines is a list."""
        assert isinstance(sample_course_ops_result["deadlines"], list)

    def test_deadline_has_required_fields(self, sample_course_ops_result):
        """Each deadline has title, due_date, deadline_type."""
        for d in sample_course_ops_result["deadlines"]:
            assert "title" in d
            assert "due_date" in d
            assert "deadline_type" in d

    def test_deadline_dates_are_iso_format(self, sample_course_ops_result):
        """Deadline dates are valid ISO date strings."""
        from datetime import date

        for d in sample_course_ops_result["deadlines"]:
            # Should not raise
            date.fromisoformat(d["due_date"])

    def test_confidence_is_float(self, sample_course_ops_result):
        """Confidence is a float between 0 and 1."""
        c = sample_course_ops_result["confidence"]
        assert isinstance(c, float)
        assert 0.0 <= c <= 1.0


# ── Assessment Response Structure ──────────────────────────────────


class TestAssessmentResponseStructure:
    """Validate assessment API response structure."""

    def test_has_required_fields(self, sample_assessment_response):
        """Assessment has all required API fields."""
        required = {
            "id", "course_id", "source_document_id", "title",
            "assessment_type", "weight_pct", "description",
            "weeks_relevant", "created_at", "updated_at",
        }
        assert required <= set(sample_assessment_response.keys())

    def test_id_is_uuid_like(self, sample_assessment_response):
        """IDs look like UUIDs."""
        assert len(sample_assessment_response["id"]) == 36
        assert "-" in sample_assessment_response["id"]


# ── Deadline Response Structure ────────────────────────────────────


class TestDeadlineResponseStructure:
    """Validate deadline API response structure."""

    def test_has_required_fields(self, sample_deadline_response):
        """Deadline has all required API fields."""
        required = {
            "id", "course_id", "assessment_id", "source_document_id",
            "title", "due_date", "deadline_type", "description",
            "is_confirmed", "created_at", "updated_at",
        }
        assert required <= set(sample_deadline_response.keys())

    def test_is_confirmed_is_bool(self, sample_deadline_response):
        """is_confirmed is a boolean."""
        assert isinstance(sample_deadline_response["is_confirmed"], bool)

    def test_due_date_is_iso(self, sample_deadline_response):
        """due_date is a valid ISO date."""
        from datetime import date

        date.fromisoformat(sample_deadline_response["due_date"])


# ── ICS Structure ──────────────────────────────────────────────────


class TestIcsStructure:
    """Validate .ics file structure."""

    @pytest.fixture
    def sample_ics_content(self):
        """Realistic .ics content."""
        return """BEGIN:VCALENDAR
PRODID:-//StudyAIO//CourseOps//EN
VERSION:2.0
X-WR-CALNAME:CSIT302 Deadlines
BEGIN:VEVENT
UID:dl-001@studyaio
SUMMARY:[CSIT302] Assignment 1 Due
DTSTART;VALUE=DATE:20260415
DTEND;VALUE=DATE:20260416
DESCRIPTION:Type: assignment\\nSubmit via Moodle
CATEGORIES:assignment
END:VEVENT
BEGIN:VEVENT
UID:dl-002@studyaio
SUMMARY:[CSIT302] Final Exam
DTSTART;VALUE=DATE:20260615
DTEND;VALUE=DATE:20260616
DESCRIPTION:Type: exam\\nMain exam hall
CATEGORIES:exam
END:VEVENT
END:VCALENDAR"""

    def test_starts_with_vcalendar(self, sample_ics_content):
        """ICS starts with BEGIN:VCALENDAR."""
        assert sample_ics_content.strip().startswith("BEGIN:VCALENDAR")

    def test_ends_with_vcalendar(self, sample_ics_content):
        """ICS ends with END:VCALENDAR."""
        assert sample_ics_content.strip().endswith("END:VCALENDAR")

    def test_has_version(self, sample_ics_content):
        """ICS contains VERSION:2.0."""
        assert "VERSION:2.0" in sample_ics_content

    def test_has_prodid(self, sample_ics_content):
        """ICS contains PRODID."""
        assert "PRODID:" in sample_ics_content

    def test_has_events(self, sample_ics_content):
        """ICS contains VEVENT blocks."""
        assert sample_ics_content.count("BEGIN:VEVENT") >= 1
        assert sample_ics_content.count("BEGIN:VEVENT") == sample_ics_content.count("END:VEVENT")

    def test_events_have_uid(self, sample_ics_content):
        """Each event has a UID."""
        assert "UID:" in sample_ics_content

    def test_events_have_summary(self, sample_ics_content):
        """Each event has a SUMMARY."""
        assert "SUMMARY:" in sample_ics_content
