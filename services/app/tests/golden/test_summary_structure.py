"""Golden tests for summary markdown structure.

Validates that summaries contain all 8 required sections defined in CLAUDE.md:
1. Title: `# <Course> — Week <N>: <Topic>`
2. `## Key Concepts`
3. `## Definitions` (table: Term | Definition)
4. `## Code Examples` (if applicable)
5. `## Diagrams & Figures` (embedded images with captions)
6. `## Potential Exam Topics`
7. `## Summary` (2-3 paragraph overview)
8. Footer with metadata: sources, version number
"""

import re

import pytest


# ── Section detection patterns ───────────────────────────────────────

TITLE_PATTERN = re.compile(r"^# .+ — Week \d+: .+", re.MULTILINE)
KEY_CONCEPTS_PATTERN = re.compile(r"^## Key Concepts", re.MULTILINE)
DEFINITIONS_PATTERN = re.compile(r"^## Definitions", re.MULTILINE)
CODE_EXAMPLES_PATTERN = re.compile(r"^## Code Examples", re.MULTILINE)
DIAGRAMS_PATTERN = re.compile(r"^## Diagrams & Figures", re.MULTILINE)
EXAM_TOPICS_PATTERN = re.compile(r"^## Potential Exam Topics", re.MULTILINE)
SUMMARY_SECTION_PATTERN = re.compile(r"^## Summary", re.MULTILINE)
FOOTER_PATTERN = re.compile(r"\*\*Sources:\*\*.*\*\*Version:\*\*", re.MULTILINE)

DEFINITIONS_TABLE_PATTERN = re.compile(
    r"\| *Term *\| *Definition *\|", re.MULTILINE | re.IGNORECASE
)

ALL_REQUIRED_SECTIONS = [
    ("Title", TITLE_PATTERN),
    ("Key Concepts", KEY_CONCEPTS_PATTERN),
    ("Definitions", DEFINITIONS_PATTERN),
    ("Code Examples", CODE_EXAMPLES_PATTERN),
    ("Diagrams & Figures", DIAGRAMS_PATTERN),
    ("Potential Exam Topics", EXAM_TOPICS_PATTERN),
    ("Summary", SUMMARY_SECTION_PATTERN),
    ("Footer", FOOTER_PATTERN),
]


# ── Tests ────────────────────────────────────────────────────────────


class TestSummaryRequiredSections:
    """Verify all 8 required sections are present in a valid summary."""

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


class TestSummaryKeyConceptsList:
    """Validate Key Concepts contains a bulleted list."""

    def test_key_concepts_has_bullets(self, sample_summary_md):
        in_section = False
        bullet_count = 0
        for line in sample_summary_md.split("\n"):
            if KEY_CONCEPTS_PATTERN.match(line):
                in_section = True
                continue
            if in_section:
                if line.startswith("## "):
                    break
                if line.strip().startswith("- "):
                    bullet_count += 1
        assert bullet_count >= 1, "Key Concepts must have at least one bullet point"


class TestSummaryFooter:
    """Validate the footer metadata section."""

    def test_footer_has_sources(self, sample_summary_md):
        assert re.search(r"\*\*Sources:\*\*", sample_summary_md)

    def test_footer_has_version(self, sample_summary_md):
        assert re.search(r"\*\*Version:\*\* *\d+", sample_summary_md)


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
