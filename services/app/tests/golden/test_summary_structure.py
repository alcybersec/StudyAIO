"""Golden tests for summary markdown structure.

Validates the v2.0 format defined by `prompts/summarize.txt`:

1. Title: `# <Course> — Week <N>: <Topic>`
2. `## Overview`
3. `## Key Concepts` (hierarchical `###`/`####` subsections)
4. `## Definitions` (table: Term | Definition)
5. `## Diagrams & Visual Descriptions`
6. `## Code Examples`
7. `## Formulas & Algorithms`
8. `## Key Takeaways`
9. `## Connections`
10. Footer: `---` then `*Sources: … Version: N.*`

`TestPromptContract` re-derives that list from the prompt file on every run, so
editing the prompt without updating these expectations fails the suite instead
of silently leaving the golden test guarding a stale format.
"""

import re
from pathlib import Path

import pytest

PROMPT_PATH = Path(__file__).parents[2] / "prompts" / "summarize.txt"

# ── Section detection patterns ───────────────────────────────────────

TITLE_PATTERN = re.compile(r"^# .+ — Week \d+: .+", re.MULTILINE)
OVERVIEW_PATTERN = re.compile(r"^## Overview", re.MULTILINE)
KEY_CONCEPTS_PATTERN = re.compile(r"^## Key Concepts", re.MULTILINE)
DEFINITIONS_PATTERN = re.compile(r"^## Definitions", re.MULTILINE)
DIAGRAMS_PATTERN = re.compile(r"^## Diagrams & Visual Descriptions", re.MULTILINE)
CODE_EXAMPLES_PATTERN = re.compile(r"^## Code Examples", re.MULTILINE)
FORMULAS_PATTERN = re.compile(r"^## Formulas & Algorithms", re.MULTILINE)
TAKEAWAYS_PATTERN = re.compile(r"^## Key Takeaways", re.MULTILINE)
CONNECTIONS_PATTERN = re.compile(r"^## Connections", re.MULTILINE)
FOOTER_PATTERN = re.compile(r"^\*Sources:.*Version: *\d+\.\*", re.MULTILINE)

DEFINITIONS_TABLE_PATTERN = re.compile(
    r"\| *Term *\| *Definition *\|", re.MULTILINE | re.IGNORECASE
)

# The `##` sections the prompt requires, in order. Title and footer are checked
# separately — they are not `##` headers.
REQUIRED_SECTION_TITLES = [
    "Overview",
    "Key Concepts",
    "Definitions",
    "Diagrams & Visual Descriptions",
    "Code Examples",
    "Formulas & Algorithms",
    "Key Takeaways",
    "Connections",
]

ALL_REQUIRED_SECTIONS = [
    ("Title", TITLE_PATTERN),
    ("Overview", OVERVIEW_PATTERN),
    ("Key Concepts", KEY_CONCEPTS_PATTERN),
    ("Definitions", DEFINITIONS_PATTERN),
    ("Diagrams & Visual Descriptions", DIAGRAMS_PATTERN),
    ("Code Examples", CODE_EXAMPLES_PATTERN),
    ("Formulas & Algorithms", FORMULAS_PATTERN),
    ("Key Takeaways", TAKEAWAYS_PATTERN),
    ("Connections", CONNECTIONS_PATTERN),
    ("Footer", FOOTER_PATTERN),
]

# Matches the numbered "Output Requirements" entries in the prompt that name a
# `## Section` — e.g. ``2. `## Overview` — 1-2 paragraphs …``
PROMPT_SECTION_PATTERN = re.compile(r"^\d+\.\s+`##\s+([^`]+)`", re.MULTILINE)


def _prompt_text() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


# ── Tests ────────────────────────────────────────────────────────────


class TestPromptContract:
    """Tie these expectations to the prompt that actually generates summaries.

    Without this, the golden test only ever asserts things about its own
    fixture and passes no matter what the prompt says.
    """

    def test_prompt_file_exists(self):
        assert PROMPT_PATH.is_file(), f"Summarize prompt not found at {PROMPT_PATH}"

    def test_prompt_sections_match_expectations(self):
        found = PROMPT_SECTION_PATTERN.findall(_prompt_text())
        assert found == REQUIRED_SECTION_TITLES, (
            "prompts/summarize.txt no longer requests the sections this golden "
            f"test checks.\n  prompt: {found}\n  test:   {REQUIRED_SECTION_TITLES}\n"
            "Update REQUIRED_SECTION_TITLES, the patterns, and the "
            "sample_summary_md fixture together."
        )

    def test_prompt_requests_the_title_format(self):
        assert re.search(
            r"^1\.\s+`#\s+\{\{ course_code \}\} — Week \{\{ week \}\}: <Topic>`",
            _prompt_text(),
            re.MULTILINE,
        ), "Prompt no longer requests the '# <Course> — Week <N>: <Topic>' title"

    def test_prompt_requests_the_footer_format(self):
        assert re.search(r"`\*Sources: .*Version: 1\.\*`", _prompt_text()), (
            "Prompt no longer requests the '*Sources: … Version: N.*' footer"
        )

    @pytest.mark.parametrize("section", REQUIRED_SECTION_TITLES)
    def test_fixture_covers_every_prompt_section(self, sample_summary_md, section):
        """The fixture must exercise every section the prompt asks for."""
        assert re.search(rf"^## {re.escape(section)}$", sample_summary_md, re.MULTILINE), (
            f"sample_summary_md is missing the '{section}' section"
        )


class TestSummaryRequiredSections:
    """Verify all required sections are present in a valid summary."""

    @pytest.mark.parametrize(
        "section_name,pattern",
        ALL_REQUIRED_SECTIONS,
        ids=[s[0] for s in ALL_REQUIRED_SECTIONS],
    )
    def test_section_present(self, sample_summary_md, section_name, pattern):
        assert pattern.search(sample_summary_md), (
            f"Summary missing required section: {section_name}"
        )


class TestSummaryTitle:
    """Validate the title section format."""

    def test_title_format(self, sample_summary_md):
        match = TITLE_PATTERN.search(sample_summary_md)
        assert match is not None
        title = match.group(0)
        # Should contain course code, week number, and topic
        assert "CSIT302" in title
        assert "Week 5" in title

    def test_title_is_first_line(self, sample_summary_md):
        first_line = sample_summary_md.strip().split("\n")[0]
        assert first_line.startswith("# ")
        assert TITLE_PATTERN.match(first_line)


class TestSummaryDefinitionsTable:
    """Validate the definitions section contains a markdown table."""

    def test_definitions_has_table(self, sample_summary_md):
        assert DEFINITIONS_TABLE_PATTERN.search(sample_summary_md), (
            "Definitions section must contain a Term | Definition table"
        )

    def test_definitions_table_has_rows(self, sample_summary_md):
        # Find lines after the definitions header that contain | separators
        in_definitions = False
        table_rows = 0
        for line in sample_summary_md.split("\n"):
            if DEFINITIONS_PATTERN.match(line):
                in_definitions = True
                continue
            if in_definitions:
                if line.startswith("## "):
                    break
                if "|" in line and "---" not in line and "Term" not in line:
                    table_rows += 1
        assert table_rows >= 1, "Definitions table must have at least one data row"


class TestSummaryKeyConcepts:
    """Key Concepts is the core section and must be hierarchical.

    v2.0 of the prompt explicitly rejects a flat bullet dump here, so this
    checks for `###`/`####` subsections rather than bullets.
    """

    def test_key_concepts_has_subsections(self, sample_summary_md):
        section = _section_body(sample_summary_md, "Key Concepts")
        subsections = re.findall(r"^#{3,4} .+", section, re.MULTILINE)
        assert len(subsections) >= 1, "Key Concepts must be organized into ### / #### subsections"

    def test_key_concepts_is_the_longest_section(self, sample_summary_md):
        """The prompt says Key Concepts 'should be the longest section'."""
        lengths = {
            name: len(_section_body(sample_summary_md, name)) for name in REQUIRED_SECTION_TITLES
        }
        longest = max(lengths, key=lambda k: lengths[k])
        assert longest == "Key Concepts", (
            f"Key Concepts should be the longest section, but '{longest}' is longer"
        )


class TestSummaryFooter:
    """Validate the footer metadata line."""

    def test_footer_has_sources(self, sample_summary_md):
        assert re.search(r"^\*Sources: ", sample_summary_md, re.MULTILINE)

    def test_footer_has_version(self, sample_summary_md):
        assert re.search(r"Version: *\d+\.\*", sample_summary_md)

    def test_footer_follows_a_horizontal_rule(self, sample_summary_md):
        assert re.search(r"^---\n\*Sources:", sample_summary_md, re.MULTILINE), (
            "Footer must be preceded by a '---' horizontal rule"
        )


class TestSummarySectionOrdering:
    """Verify sections appear in the correct order."""

    def test_sections_in_order(self, sample_summary_md):
        positions = []
        for name, pattern in ALL_REQUIRED_SECTIONS:
            match = pattern.search(sample_summary_md)
            if match:
                positions.append((name, match.start()))
            else:
                pytest.fail(f"Missing section: {name}")

        for i in range(len(positions) - 1):
            current_name, current_pos = positions[i]
            next_name, next_pos = positions[i + 1]
            assert current_pos < next_pos, (
                f"Section '{current_name}' (pos {current_pos}) should appear "
                f"before '{next_name}' (pos {next_pos})"
            )


# ── Helpers ──────────────────────────────────────────────────────────


def _section_body(markdown: str, section_title: str) -> str:
    """Return the body of a `## <section_title>` section, up to the next `##`."""
    match = re.search(rf"^## {re.escape(section_title)}$", markdown, re.MULTILINE)
    if not match:
        return ""
    rest = markdown[match.end() :]
    next_section = re.search(r"^## ", rest, re.MULTILINE)
    return rest[: next_section.start()] if next_section else rest
