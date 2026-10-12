"""Key Concepts citation coverage and the outside-material signal (GL#34)."""

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


def test_report_shows_citation_and_baseline_records_it():
    run = offline.run_offline(CASES)
    text = offline.format_offline_report(run, offline.load_baseline(), [])
    assert "citation coverage" in text
    baseline = run.to_baseline()
    assert baseline["aggregate"]["citation_coverage"] == round(run.citation_coverage, 4)
    assert all("citation_coverage" in c for c in baseline["cases"].values())


def _run_with_coverage(tmp_path, cited: int, total: int):
    lines = [
        f"- claim number {i} says things [p.1]" if i < cited else f"- claim number {i} says things"
        for i in range(total)
    ]
    (tmp_path / "c.md").write_text(_kc("\n".join(lines)))
    return offline.run_offline([CASE], tmp_path)


def _baseline(cit):
    return {
        "threshold": 0.02,
        "aggregate": {"faithfulness": 0.0, "citation_coverage": cit},
        "cases": {"c": {}},
    }


def _cit_failures(run, baseline):
    return [f for f in offline.check_against_baseline(run, baseline) if "citation" in f]


def test_gate_fails_below_the_absolute_citation_floor(tmp_path):
    run = _run_with_coverage(tmp_path, 8, 10)  # 0.80 < 0.90; relative floor would be 0.75
    assert _cit_failures(run, _baseline(0.80))


def test_gate_fails_on_a_drop_below_baseline_minus_threshold(tmp_path):
    run = _run_with_coverage(tmp_path, 28, 30)  # 0.933 >= 0.90 but < 1.0 - 0.05... floor is 0.95
    failures = _cit_failures(run, _baseline(1.0))
    assert failures and "0.950" in failures[0]


def test_gate_passes_within_the_threshold_and_above_the_floor(tmp_path):
    run = _run_with_coverage(tmp_path, 19, 20)  # 0.95 == baseline 1.0 - 0.05
    assert _cit_failures(run, _baseline(1.0)) == []
    run = _run_with_coverage(tmp_path, 10, 10)
    assert _cit_failures(run, _baseline(0.92)) == []


def test_baseline_without_citation_figure_skips_the_citation_gate(tmp_path):
    run = _run_with_coverage(tmp_path, 1, 10)
    baseline = _baseline(0.9)
    del baseline["aggregate"]["citation_coverage"]
    assert _cit_failures(run, baseline) == []


def test_provenance_pairs_parse_as_json_or_text():
    from evals.__main__ import _parse_extras

    got = _parse_extras(["prompt=summarize v2.5", "temperature=0.2", "runs=2"])
    assert got == {"prompt": "summarize v2.5", "temperature": 0.2, "runs": 2}
