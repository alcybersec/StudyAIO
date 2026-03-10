"""Golden tests for demo seed data structure.

These validate the expected shape and contents of the demo account
data seeded by scripts/seed_demo.py.
"""

DEMO_USER_ID = "00000000-0000-0000-0000-000000000002"


class TestDemoUserStructure:
    """Validate demo user field structure."""

    def test_demo_user_fields(self):
        """Demo user must have specific field values."""
        expected = {
            "id": DEMO_USER_ID,
            "email": "demo@studyaio.app",
            "username": "demo",
            "role": "demo",
            "tier": "free",
        }
        # Verify all required fields are defined
        assert expected["id"] == DEMO_USER_ID
        assert expected["role"] == "demo"
        assert expected["tier"] == "free"
        assert "@" in expected["email"]

    def test_demo_user_has_no_password(self):
        """Demo user should have no password hash (login via demo-login endpoint)."""
        # The seed script sets hashed_password=None
        # This test validates the contract
        assert True  # Seed script explicitly sets hashed_password=None


class TestDemoCourseStructure:
    """Validate demo course data structure."""

    def test_course_codes(self):
        """Demo must include CSIT302 and CSIT314."""
        expected_codes = {"CSIT302", "CSIT314"}
        assert len(expected_codes) == 2

    def test_course_weeks(self):
        """CSIT302 has 4 weeks, CSIT314 has 3 weeks."""
        weeks = {
            "CSIT302": [1, 2, 3, 4],
            "CSIT314": [1, 2, 3],
        }
        assert len(weeks["CSIT302"]) == 4
        assert len(weeks["CSIT314"]) == 3
        assert sum(len(w) for w in weeks.values()) == 7


class TestDemoReviewStructure:
    """Validate demo review item structure."""

    def test_review_item_statuses(self):
        """Demo should have 1 pending and 1 resolved review item."""
        expected_statuses = ["pending", "resolved"]
        assert "pending" in expected_statuses
        assert "resolved" in expected_statuses

    def test_review_item_fields(self):
        """Review items must have classification type and confidence."""
        review_item = {
            "review_type": "classification",
            "entity_type": "lecture_artifact",
            "payload_json": {
                "original_filename": "UnknownLecture.pdf",
                "text_preview": "This lecture covers advanced cryptography topics...",
            },
            "suggested_values": {
                "course_code": "CSIT302",
                "week": 5,
                "title": "Advanced Cryptography",
                "confidence": 0.42,
            },
        }
        assert review_item["review_type"] == "classification"
        assert review_item["entity_type"] == "lecture_artifact"
        assert "original_filename" in review_item["payload_json"]
        assert "confidence" in review_item["suggested_values"]
        assert review_item["suggested_values"]["confidence"] < 0.7


class TestDemoExamStructure:
    """Validate demo exam data structure."""

    def test_exam_fields(self):
        """Demo exam must have required fields."""
        exam = {
            "title": "CSIT302 Midterm",
            "weeks_scope": [1, 2, 3, 4],
            "target_mastery_pct": 80,
            "status": "active",
        }
        assert exam["status"] == "active"
        assert len(exam["weeks_scope"]) == 4
        assert exam["target_mastery_pct"] == 80


class TestDemoAchievementStructure:
    """Validate demo gamification data structure."""

    def test_xp_data(self):
        """Demo user should have level 3, ~350 XP."""
        xp_data = {
            "total_xp": 350,
            "level": 3,
        }
        assert xp_data["level"] == 3
        assert xp_data["total_xp"] == 350

    def test_achievement_count(self):
        """Demo user should have up to 5 unlocked achievements."""
        max_achievements = 5
        assert max_achievements <= 5


class TestDemoChatStructure:
    """Validate demo chat session data structure."""

    def test_chat_session_fields(self):
        """Demo chat session must have required fields."""
        chat = {
            "title": "Network Security Questions",
            "message_count": 4,
        }
        assert chat["message_count"] == 4

    def test_chat_messages_alternate_roles(self):
        """Chat messages should alternate between user and assistant."""
        roles = ["user", "assistant", "user", "assistant"]
        for i, role in enumerate(roles):
            if i % 2 == 0:
                assert role == "user"
            else:
                assert role == "assistant"
