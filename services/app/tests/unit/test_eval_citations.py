"""Key Concepts citation coverage and the outside-material signal (GL#34)."""

import json

from evals import offline, runner

CASES = runner.load_cases()

CASE = {
    "id": "c",
    "pages": [{"page": 1, "text": "Stacks are LIFO. Queues are FIFO."}],
}


def _kc(body: str) -> str:
    return (
        f"# C — Week 1: T\n\n## Overview\n\nx\n\n## Key Concepts\n\n{body}\n\n## Definitions\n\nx\n"
    )


def test_claims_split_bullets_rows_and_paragraphs():
    body = (
        "### Heading\n\nA stack removes the newest item first [p.1].\n\n"
        "- Queues remove the oldest item first [p.1]\n"
        "- Short one\n\n"
        "| Term | Meaning |\n|---|---|\n| LIFO | last in, first out [p.1] |\n\n"
        "```\ncode here is not a claim at all\n```\n"
    )
    assert len(offline.key_concepts_claims(_kc(body))) == 3


def test_coverage_counts_only_cited_claims():
    body = "- A stack is last in first out [p.1]\n- A queue is first in first out"
    rep = offline.check_citations(CASE, _kc(body))
    assert (rep.claims, rep.cited) == (2, 1)
    assert rep.coverage == 0.5


def test_marker_for_missing_page_is_invalid_not_cited():
    rep = offline.check_citations(CASE, _kc("- A stack is last in first out [p.9]"))
    assert rep.cited == 0
    assert rep.invalid_markers == ["[p.9]"]


def test_multi_document_marker_and_range_accepted():
    case = {"id": "c", "pages": [{"page": 1, "text": "a"}, {"page": 2, "text": "b"}]}
    rep = offline.check_citations(case, _kc("- A stack is last in first out [D2 p.1-2]"))
    assert rep.cited == 1


def test_term_absent_from_source_is_flagged():
    rep = offline.check_citations(CASE, _kc("- A stack is LIFO and AVL trees rebalance [p.1]"))
    assert rep.ungrounded_terms == ["AVL"]


def test_term_present_in_source_is_not_flagged():
    rep = offline.check_citations(CASE, _kc("- A stack is LIFO and a queue is FIFO [p.1]"))
    assert rep.ungrounded_terms == []


def test_no_key_concepts_means_no_claims():
    assert offline.check_citations(CASE, "# C — Week 1: T\n").coverage == 1.0


def test_report_shows_citation_and_baseline_ignores_it():
    run = offline.run_offline(CASES)
    text = offline.format_offline_report(run, offline.load_baseline(), [])
    assert "citation coverage" in text
    assert "citation" not in json.dumps(run.to_baseline())
