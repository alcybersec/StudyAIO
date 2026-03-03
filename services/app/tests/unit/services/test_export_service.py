"""Tests for export_service (Obsidian vault generation)."""

import zipfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.export_service import (
    _generate_flashcards_md,
    _generate_index_md,
    _generate_quizzes_md,
    _generate_week_md,
    _yaml_frontmatter,
    generate_obsidian_vault,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_course(code: str = "CSIT302", name: str = "Cybersecurity") -> MagicMock:
    """Create a mock Course object."""
    course = MagicMock()
    course.id = "course-001"
    course.code = code
    course.name = name
    return course


def _make_summary(week: int, content: str = "# Summary content") -> MagicMock:
    """Create a mock Summary object."""
    summary = MagicMock()
    summary.week = week
    summary.content_md = content
    return summary


def _make_flashcard(week: int, front: str, back: str) -> MagicMock:
    """Create a mock Flashcard object."""
    fc = MagicMock()
    fc.week = week
    fc.front = front
    fc.back = back
    return fc


def _make_quiz(
    week: int,
    question: str,
    question_type: str = "multiple_choice",
    options: list[str] | None = None,
    correct_answer: str = "B",
    explanation: str = "Because B is correct.",
) -> MagicMock:
    """Create a mock QuizQuestion object."""
    q = MagicMock()
    q.week = week
    q.question = question
    q.question_type = question_type
    q.options_json = options
    q.correct_answer = correct_answer
    q.explanation = explanation
    return q


def _mock_session_for_vault(
    course: MagicMock | None,
    summaries: list[MagicMock] | None = None,
    flashcards: list[MagicMock] | None = None,
    quizzes: list[MagicMock] | None = None,
) -> AsyncMock:
    """Build a mock session that returns the given data.

    The session.execute is called 4 times in generate_obsidian_vault:
    1. Course lookup (scalar_one_or_none)
    2. Summary query (scalars().all())
    3. Flashcard query (scalars().all())
    4. Quiz query (scalars().all())
    """
    session = AsyncMock()

    # Call 1: course lookup
    course_result = MagicMock()
    course_result.scalar_one_or_none.return_value = course

    # Call 2: summaries
    summary_result = MagicMock()
    summary_result.scalars.return_value.all.return_value = summaries or []

    # Call 3: flashcards
    fc_result = MagicMock()
    fc_result.scalars.return_value.all.return_value = flashcards or []

    # Call 4: quizzes
    qq_result = MagicMock()
    qq_result.scalars.return_value.all.return_value = quizzes or []

    session.execute = AsyncMock(
        side_effect=[course_result, summary_result, fc_result, qq_result]
    )
    return session


# ── Unit tests: helper functions ─────────────────────────────────────


class TestYamlFrontmatter:
    """Tests for _yaml_frontmatter helper."""

    def test_simple_metadata(self):
        result = _yaml_frontmatter({"type": "index", "course": "CSIT302"})
        assert result.startswith("---")
        assert result.endswith("---")
        assert "type: index" in result
        assert "course: CSIT302" in result

    def test_list_values(self):
        result = _yaml_frontmatter({"tags": ["alpha", "beta"]})
        assert "tags:" in result
        assert "  - alpha" in result
        assert "  - beta" in result


class TestGenerateIndexMd:
    """Tests for _generate_index_md helper."""

    def test_index_contains_course_code(self):
        course = _make_course()
        result = _generate_index_md(course, [1, 2, 3])
        assert "# CSIT302" in result

    def test_index_contains_week_links(self):
        course = _make_course()
        result = _generate_index_md(course, [1, 5])
        assert "[[Week01|Week 1]]" in result
        assert "[[Week05|Week 5]]" in result

    def test_index_contains_resource_links(self):
        course = _make_course()
        result = _generate_index_md(course, [1])
        assert "[[Flashcards/|Flashcards]]" in result
        assert "[[Quizzes/|Quizzes]]" in result


class TestGenerateWeekMd:
    """Tests for _generate_week_md helper."""

    def test_week_with_summary(self):
        summary = _make_summary(3, "# Week 3 content here")
        result = _generate_week_md("CSIT302", 3, summary)
        assert "# Week 3 content here" in result

    def test_week_without_summary(self):
        result = _generate_week_md("CSIT302", 3, None)
        assert "No summary available yet" in result

    def test_week_has_wiki_links(self):
        result = _generate_week_md("CSIT302", 3, None)
        assert "[[Flashcards/Week03|View Flashcards]]" in result
        assert "[[Quizzes/Week03|View Quizzes]]" in result
        assert "[[_Index|Back to CSIT302]]" in result


class TestGenerateFlashcardsMd:
    """Tests for _generate_flashcards_md helper."""

    def test_flashcards_use_callout(self):
        fc = _make_flashcard(1, "What is DNS?", "Domain Name System")
        result = _generate_flashcards_md("CSIT302", 1, [fc])
        assert "> [!question] What is DNS?" in result
        assert "> Domain Name System" in result

    def test_flashcards_empty_week(self):
        result = _generate_flashcards_md("CSIT302", 1, [])
        assert "No flashcards available for this week" in result

    def test_flashcards_back_link(self):
        result = _generate_flashcards_md("CSIT302", 5, [])
        assert "[[../Week05|Back to Week 5]]" in result


class TestGenerateQuizzesMd:
    """Tests for _generate_quizzes_md helper."""

    def test_quizzes_have_collapsible_answers(self):
        q = _make_quiz(1, "Which protocol?", "multiple_choice",
                       ["A. TCP", "B. UDP", "C. HTTP", "D. FTP"], "B", "UDP is connectionless")
        result = _generate_quizzes_md("CSIT302", 1, [q])
        assert "> [!success]- Answer" in result
        assert "> **B**" in result
        assert "> UDP is connectionless" in result

    def test_quizzes_show_options(self):
        q = _make_quiz(1, "Which is fastest?", "multiple_choice",
                       ["A. TCP", "B. UDP"], "B. UDP", "UDP has no overhead")
        result = _generate_quizzes_md("CSIT302", 1, [q])
        assert "- A. TCP" in result
        assert "- B. UDP" in result

    def test_quizzes_empty_week(self):
        result = _generate_quizzes_md("CSIT302", 1, [])
        assert "No quiz questions available for this week" in result

    def test_quizzes_short_answer_no_options(self):
        q = _make_quiz(1, "Explain TCP.", "short_answer",
                       None, "TCP is a connection-oriented protocol.", "It ensures reliable delivery.")
        result = _generate_quizzes_md("CSIT302", 1, [q])
        assert "Short Answer" in result
        # Should not have option list items (no "- " lines for options)
        assert "- A." not in result


# ── Unit tests: generate_obsidian_vault ──────────────────────────────


@pytest.mark.asyncio
class TestGenerateObsidianVault:
    """Tests for generate_obsidian_vault main function."""

    async def test_generate_vault_returns_zip(self):
        """Valid course returns a zip archive."""
        course = _make_course()
        summary = _make_summary(1, "# Week 1 summary")
        fc = _make_flashcard(1, "Q?", "A.")
        qq = _make_quiz(1, "What?", "short_answer", None, "Answer.", "Explanation.")

        session = _mock_session_for_vault(course, [summary], [fc], [qq])
        result = await generate_obsidian_vault(session, "CSIT302")

        assert result is not None
        buf, filename = result
        assert filename == "CSIT302_vault.zip"

        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            assert len(names) > 0

    async def test_generate_vault_course_not_found(self):
        """Returns None when course does not exist."""
        session = AsyncMock()
        course_result = MagicMock()
        course_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=course_result)

        result = await generate_obsidian_vault(session, "NONEXIST")
        assert result is None

    async def test_vault_contains_index(self):
        """Zip archive contains _Index.md."""
        course = _make_course()
        summary = _make_summary(1)
        session = _mock_session_for_vault(course, [summary])

        result = await generate_obsidian_vault(session, "CSIT302")
        assert result is not None
        buf, _ = result

        with zipfile.ZipFile(buf) as zf:
            assert "CSIT302/_Index.md" in zf.namelist()

    async def test_vault_contains_week_files(self):
        """Zip archive contains WeekNN.md files."""
        course = _make_course()
        summary = _make_summary(3, "# Week 3")
        session = _mock_session_for_vault(course, [summary])

        result = await generate_obsidian_vault(session, "CSIT302")
        assert result is not None
        buf, _ = result

        with zipfile.ZipFile(buf) as zf:
            assert "CSIT302/Week03.md" in zf.namelist()

    async def test_vault_contains_flashcards(self):
        """Zip archive contains Flashcards/WeekNN.md files."""
        course = _make_course()
        fc = _make_flashcard(2, "Q?", "A.")
        session = _mock_session_for_vault(course, [], [fc])

        result = await generate_obsidian_vault(session, "CSIT302")
        assert result is not None
        buf, _ = result

        with zipfile.ZipFile(buf) as zf:
            assert "CSIT302/Flashcards/Week02.md" in zf.namelist()

    async def test_vault_contains_quizzes(self):
        """Zip archive contains Quizzes/WeekNN.md files."""
        course = _make_course()
        qq = _make_quiz(4, "What?", "short_answer", None, "Answer.", "Expl.")
        session = _mock_session_for_vault(course, [], [], [qq])

        result = await generate_obsidian_vault(session, "CSIT302")
        assert result is not None
        buf, _ = result

        with zipfile.ZipFile(buf) as zf:
            assert "CSIT302/Quizzes/Week04.md" in zf.namelist()

    async def test_index_has_frontmatter(self):
        """_Index.md starts with YAML frontmatter."""
        course = _make_course()
        summary = _make_summary(1)
        session = _mock_session_for_vault(course, [summary])

        result = await generate_obsidian_vault(session, "CSIT302")
        assert result is not None
        buf, _ = result

        with zipfile.ZipFile(buf) as zf:
            content = zf.read("CSIT302/_Index.md").decode()
            assert content.startswith("---")

    async def test_week_file_has_wiki_links(self):
        """Week file contains wiki-links to flashcards and quizzes."""
        course = _make_course()
        summary = _make_summary(5, "# Week 5")
        session = _mock_session_for_vault(course, [summary])

        result = await generate_obsidian_vault(session, "CSIT302")
        assert result is not None
        buf, _ = result

        with zipfile.ZipFile(buf) as zf:
            content = zf.read("CSIT302/Week05.md").decode()
            assert "[[Flashcards/Week05|View Flashcards]]" in content
            assert "[[Quizzes/Week05|View Quizzes]]" in content

    async def test_flashcards_use_callout_in_vault(self):
        """Flashcard file in vault uses Obsidian callout syntax."""
        course = _make_course()
        fc = _make_flashcard(1, "What is TCP?", "Transmission Control Protocol")
        session = _mock_session_for_vault(course, [], [fc])

        result = await generate_obsidian_vault(session, "CSIT302")
        assert result is not None
        buf, _ = result

        with zipfile.ZipFile(buf) as zf:
            content = zf.read("CSIT302/Flashcards/Week01.md").decode()
            assert "> [!question] What is TCP?" in content

    async def test_quizzes_have_collapsible_answers_in_vault(self):
        """Quiz file in vault uses collapsible answer syntax."""
        course = _make_course()
        qq = _make_quiz(1, "Which layer?", "multiple_choice",
                        ["A. 1", "B. 2", "C. 3", "D. 4"], "C. 3", "Layer 3 is network.")
        session = _mock_session_for_vault(course, [], [], [qq])

        result = await generate_obsidian_vault(session, "CSIT302")
        assert result is not None
        buf, _ = result

        with zipfile.ZipFile(buf) as zf:
            content = zf.read("CSIT302/Quizzes/Week01.md").decode()
            assert "> [!success]- Answer" in content

    async def test_vault_with_week_filter(self):
        """Passing weeks parameter filters output."""
        course = _make_course()
        s1 = _make_summary(1, "# Week 1")
        s3 = _make_summary(3, "# Week 3")
        session = _mock_session_for_vault(course, [s1, s3])

        result = await generate_obsidian_vault(session, "CSIT302", weeks=[1, 3])
        assert result is not None
        buf, _ = result

        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            assert "CSIT302/Week01.md" in names
            assert "CSIT302/Week03.md" in names
            # Week 2 should not be present
            assert "CSIT302/Week02.md" not in names

    async def test_vault_empty_course_no_weeks(self):
        """Course with no data produces zip with only index."""
        course = _make_course()
        session = _mock_session_for_vault(course)

        result = await generate_obsidian_vault(session, "CSIT302")
        assert result is not None
        buf, _ = result

        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            assert "CSIT302/_Index.md" in names
            # Only the index file should exist
            assert len(names) == 1
