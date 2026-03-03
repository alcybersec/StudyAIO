"""Golden tests for Obsidian vault export structure.

Validates that generated Obsidian vaults conform to expected structure:
- Correct file paths in zip archive
- Valid YAML frontmatter blocks
- Obsidian wiki-link syntax ([[...]])
- Callout blocks for flashcards (> [!question])
- Collapsible answers for quizzes (> [!success]- Answer)
"""

import re
import zipfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.export_service import generate_obsidian_vault


# ── Fixtures ────────────────────────────────────────────────────────


def _make_course(code: str = "CSIT302", name: str = "Cybersecurity") -> MagicMock:
    """Create a mock Course object."""
    course = MagicMock()
    course.id = "course-001"
    course.code = code
    course.name = name
    return course


def _make_summary(week: int, content: str) -> MagicMock:
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
    explanation: str = "Explanation here.",
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


def _build_mock_session(
    course: MagicMock | None,
    summaries: list | None = None,
    flashcards: list | None = None,
    quizzes: list | None = None,
) -> AsyncMock:
    """Build a mock session returning the given data."""
    session = AsyncMock()

    course_result = MagicMock()
    course_result.scalar_one_or_none.return_value = course

    summary_result = MagicMock()
    summary_result.scalars.return_value.all.return_value = summaries or []

    fc_result = MagicMock()
    fc_result.scalars.return_value.all.return_value = flashcards or []

    qq_result = MagicMock()
    qq_result.scalars.return_value.all.return_value = quizzes or []

    session.execute = AsyncMock(
        side_effect=[course_result, summary_result, fc_result, qq_result]
    )
    return session


@pytest.fixture
def sample_vault_data():
    """Complete sample data for vault generation."""
    course = _make_course("CSIT302", "Cybersecurity")
    summaries = [
        _make_summary(1, "# CSIT302 -- Week 1: Intro\n\n## Key Concepts\n- Security basics"),
        _make_summary(2, "# CSIT302 -- Week 2: Networks\n\n## Key Concepts\n- TCP/IP"),
    ]
    flashcards = [
        _make_flashcard(1, "What is CIA triad?", "Confidentiality, Integrity, Availability"),
        _make_flashcard(1, "Define authentication.", "Verifying identity of a user or system."),
        _make_flashcard(2, "What is TCP?", "Transmission Control Protocol"),
    ]
    quizzes = [
        _make_quiz(
            1, "Which is NOT part of CIA triad?", "multiple_choice",
            ["A. Confidentiality", "B. Integrity", "C. Availability", "D. Scalability"],
            "D. Scalability", "CIA stands for Confidentiality, Integrity, Availability.",
        ),
        _make_quiz(
            2, "Explain the TCP three-way handshake.", "short_answer",
            None, "SYN, SYN-ACK, ACK sequence to establish connection.",
            "TCP uses a three-way handshake for reliable connection setup.",
        ),
    ]
    return course, summaries, flashcards, quizzes


# ── Golden structure tests ──────────────────────────────────────────


@pytest.mark.asyncio
class TestVaultStructure:
    """Verify all expected paths exist in the zip archive."""

    async def test_vault_has_all_expected_paths(self, sample_vault_data):
        """Zip contains index, week files, flashcard files, and quiz files."""
        course, summaries, flashcards, quizzes = sample_vault_data
        session = _build_mock_session(course, summaries, flashcards, quizzes)

        result = await generate_obsidian_vault(session, "CSIT302")
        assert result is not None
        buf, filename = result

        with zipfile.ZipFile(buf) as zf:
            names = set(zf.namelist())

        expected_paths = {
            "CSIT302/_Index.md",
            "CSIT302/Week01.md",
            "CSIT302/Week02.md",
            "CSIT302/Flashcards/Week01.md",
            "CSIT302/Flashcards/Week02.md",
            "CSIT302/Quizzes/Week01.md",
            "CSIT302/Quizzes/Week02.md",
        }
        missing = expected_paths - names
        assert not missing, f"Missing paths in vault: {missing}"

    async def test_vault_no_extra_top_level_dirs(self, sample_vault_data):
        """All paths are under the course code directory."""
        course, summaries, flashcards, quizzes = sample_vault_data
        session = _build_mock_session(course, summaries, flashcards, quizzes)

        result = await generate_obsidian_vault(session, "CSIT302")
        buf, _ = result

        with zipfile.ZipFile(buf) as zf:
            for name in zf.namelist():
                assert name.startswith("CSIT302/"), f"Path {name} not under CSIT302/"


@pytest.mark.asyncio
class TestFrontmatterFormat:
    """Verify YAML frontmatter block format."""

    async def test_all_md_files_have_frontmatter(self, sample_vault_data):
        """Every .md file in the vault starts with YAML frontmatter."""
        course, summaries, flashcards, quizzes = sample_vault_data
        session = _build_mock_session(course, summaries, flashcards, quizzes)

        result = await generate_obsidian_vault(session, "CSIT302")
        buf, _ = result

        with zipfile.ZipFile(buf) as zf:
            for name in zf.namelist():
                if name.endswith(".md"):
                    content = zf.read(name).decode()
                    assert content.startswith("---"), (
                        f"{name} does not start with YAML frontmatter delimiter '---'"
                    )
                    # Must have closing delimiter
                    parts = content.split("---", 2)
                    assert len(parts) >= 3, (
                        f"{name} does not have closing frontmatter delimiter '---'"
                    )

    async def test_frontmatter_contains_type_field(self, sample_vault_data):
        """Every frontmatter block has a 'type' field."""
        course, summaries, flashcards, quizzes = sample_vault_data
        session = _build_mock_session(course, summaries, flashcards, quizzes)

        result = await generate_obsidian_vault(session, "CSIT302")
        buf, _ = result

        with zipfile.ZipFile(buf) as zf:
            for name in zf.namelist():
                if name.endswith(".md"):
                    content = zf.read(name).decode()
                    frontmatter = content.split("---")[1]
                    assert "type:" in frontmatter, (
                        f"{name} frontmatter missing 'type' field"
                    )


@pytest.mark.asyncio
class TestWikiLinksPresent:
    """Verify [[...]] wiki-links in content."""

    async def test_index_has_week_wiki_links(self, sample_vault_data):
        """Index file has wiki-links for each week."""
        course, summaries, flashcards, quizzes = sample_vault_data
        session = _build_mock_session(course, summaries, flashcards, quizzes)

        result = await generate_obsidian_vault(session, "CSIT302")
        buf, _ = result

        with zipfile.ZipFile(buf) as zf:
            content = zf.read("CSIT302/_Index.md").decode()

        assert "[[Week01|Week 1]]" in content
        assert "[[Week02|Week 2]]" in content

    async def test_week_files_have_navigation_links(self, sample_vault_data):
        """Week files have back-to-index and asset links."""
        course, summaries, flashcards, quizzes = sample_vault_data
        session = _build_mock_session(course, summaries, flashcards, quizzes)

        result = await generate_obsidian_vault(session, "CSIT302")
        buf, _ = result

        wiki_link_pattern = re.compile(r"\[\[.+?\|.+?\]\]")

        with zipfile.ZipFile(buf) as zf:
            for name in zf.namelist():
                if name.endswith(".md") and "/Week" in name and "/Flashcards/" not in name and "/Quizzes/" not in name:
                    content = zf.read(name).decode()
                    matches = wiki_link_pattern.findall(content)
                    assert len(matches) >= 3, (
                        f"{name} should have at least 3 wiki-links "
                        f"(flashcards, quizzes, index), found {len(matches)}"
                    )


@pytest.mark.asyncio
class TestFlashcardCalloutFormat:
    """Verify Obsidian callout syntax for flashcards."""

    async def test_flashcards_use_question_callout(self, sample_vault_data):
        """Flashcard files use > [!question] callout blocks."""
        course, summaries, flashcards, quizzes = sample_vault_data
        session = _build_mock_session(course, summaries, flashcards, quizzes)

        result = await generate_obsidian_vault(session, "CSIT302")
        buf, _ = result

        callout_pattern = re.compile(r">\s*\[!question\]\s+.+")

        with zipfile.ZipFile(buf) as zf:
            # Week 1 has 2 flashcards
            content = zf.read("CSIT302/Flashcards/Week01.md").decode()
            matches = callout_pattern.findall(content)
            assert len(matches) == 2, (
                f"Expected 2 callout blocks for Week 1, found {len(matches)}"
            )

    async def test_flashcard_answer_follows_question(self, sample_vault_data):
        """Each flashcard callout has an answer line starting with '> '."""
        course, summaries, flashcards, quizzes = sample_vault_data
        session = _build_mock_session(course, summaries, flashcards, quizzes)

        result = await generate_obsidian_vault(session, "CSIT302")
        buf, _ = result

        with zipfile.ZipFile(buf) as zf:
            content = zf.read("CSIT302/Flashcards/Week01.md").decode()
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "> [!question]" in line:
                    # Next line should be the answer
                    assert i + 1 < len(lines), "Answer line missing after question callout"
                    assert lines[i + 1].startswith("> "), (
                        f"Answer line should start with '> ', got: {lines[i + 1]}"
                    )


@pytest.mark.asyncio
class TestQuizAnswerFormat:
    """Verify collapsible answer syntax for quizzes."""

    async def test_quizzes_use_success_callout(self, sample_vault_data):
        """Quiz files use > [!success]- Answer callout blocks."""
        course, summaries, flashcards, quizzes = sample_vault_data
        session = _build_mock_session(course, summaries, flashcards, quizzes)

        result = await generate_obsidian_vault(session, "CSIT302")
        buf, _ = result

        with zipfile.ZipFile(buf) as zf:
            # Week 1 has 1 quiz (MCQ), Week 2 has 1 quiz (short answer)
            w1_content = zf.read("CSIT302/Quizzes/Week01.md").decode()
            w2_content = zf.read("CSIT302/Quizzes/Week02.md").decode()

        assert "> [!success]- Answer" in w1_content, "Week 1 quiz missing collapsible answer"
        assert "> [!success]- Answer" in w2_content, "Week 2 quiz missing collapsible answer"

    async def test_quiz_answer_is_bold(self, sample_vault_data):
        """Quiz answers are formatted as bold text after the callout."""
        course, summaries, flashcards, quizzes = sample_vault_data
        session = _build_mock_session(course, summaries, flashcards, quizzes)

        result = await generate_obsidian_vault(session, "CSIT302")
        buf, _ = result

        bold_answer_pattern = re.compile(r">\s+\*\*.+\*\*")

        with zipfile.ZipFile(buf) as zf:
            for name in zf.namelist():
                if "/Quizzes/" in name:
                    content = zf.read(name).decode()
                    if "> [!success]- Answer" in content:
                        matches = bold_answer_pattern.findall(content)
                        assert len(matches) >= 1, (
                            f"{name} should have bold answer text"
                        )

    async def test_mcq_quiz_has_option_list(self, sample_vault_data):
        """Multiple choice quizzes include option list items."""
        course, summaries, flashcards, quizzes = sample_vault_data
        session = _build_mock_session(course, summaries, flashcards, quizzes)

        result = await generate_obsidian_vault(session, "CSIT302")
        buf, _ = result

        with zipfile.ZipFile(buf) as zf:
            content = zf.read("CSIT302/Quizzes/Week01.md").decode()

        # Week 1 MCQ should have the 4 options as list items
        assert "- A. Confidentiality" in content
        assert "- D. Scalability" in content
