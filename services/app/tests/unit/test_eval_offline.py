"""Tests for the offline eval gate (`python -m evals --offline --check`).

The gate is what CI runs, so a scorer that waves a bad summary through here is
worse than no gate. These include a deliberately unfaithful fixture that must
fail, and a check that the committed fixtures and baseline agree.
"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from evals import __main__ as cli
from evals import offline, runner, scoring

CASES = runner.load_cases()


def _case(**kw) -> dict:
    base = {
        "id": "c",
        "course": "CSIT101",
        "week": 3,
        "pages": [{"page": 1, "text": "Stacks are LIFO. Queues are FIFO."}],
        "must_mention": ["LIFO", "FIFO"],
        "must_not_mention": ["deque"],
        "required_facts": [
            {"fact": "stack is LIFO", "all": ["stack", "LIFO"]},
            {"fact": "queue is FIFO", "all": ["queue", "FIFO"]},
        ],
        "forbidden_claims": [{"claim": "mentions priority", "pattern": r"priority"}],
    }
    base.update(kw)
    return base


def _summary(body: str = "A stack is LIFO. A queue is FIFO.", *, drop=(), title=True, footer=True):
    parts = ["# CSIT101 — Week 3: Stacks and Queues\n"] if title else []
    for name in scoring.required_sections():
        if name not in drop:
            parts.append(f"## {name}\n\n{body}\n")
    if footer:
        parts.append("---\n*Sources: a.pdf. Version: 1.*\n")
    return "\n".join(parts)


class TestStructure:
    def test_complete_summary_has_no_problems(self):
        assert offline.check_structure(_summary()) == []

    def test_missing_section_is_named(self):
        assert "missing section: Definitions" in offline.check_structure(
            _summary(drop=("Definitions",))
        )

    def test_missing_title_and_footer_are_problems(self):
        problems = offline.check_structure(_summary(title=False, footer=False))
        assert any("title" in p for p in problems)
        assert any("footer" in p for p in problems)

    def test_out_of_order_sections_are_a_problem(self):
        wanted = scoring.required_sections()
        swapped = _summary()
        a, b = f"## {wanted[0]}", f"## {wanted[1]}"
        swapped = swapped.replace(a, "@@").replace(b, a).replace("@@", b)
        assert "sections out of order" in offline.check_structure(swapped)


class TestFaithfulnessScore:
    def test_faithful_summary_scores_one(self):
        score = offline.score_offline(_case(), _summary())
        assert score.faithfulness == 1.0
        assert score.structure_ok

    def test_a_missing_fact_lowers_recall_and_is_named(self):
        score = offline.score_offline(_case(), _summary("A stack is LIFO."))
        assert score.fact_recall == 0.5
        assert score.missing_facts == ["queue is FIFO"]

    def test_all_terms_must_co_occur(self):
        """A qualified claim is not satisfied by half of it."""
        case = _case(required_facts=[{"fact": "q", "all": ["average O(1)", "worst case O(n)"]}])
        half = offline.score_offline(case, _summary("lookup is average O(1)"))
        assert half.fact_recall == 0.0

    def test_any_terms_accept_one_alternative(self):
        case = _case(required_facts=[{"fact": "x", "any": ["LIFO", "last-in"]}])
        assert offline.score_offline(case, _summary("a stack ordering")).fact_recall == 0.0
        assert offline.score_offline(case, _summary("it is LIFO")).fact_recall == 1.0

    def test_a_fact_with_no_terms_is_a_case_error(self):
        case = _case(required_facts=[{"fact": "broken"}])
        with pytest.raises(ValueError, match="neither"):
            offline.score_offline(case, _summary())

    def test_forbidden_term_halves_faithfulness(self):
        score = offline.score_offline(
            _case(), _summary("A stack is LIFO. A queue is FIFO. A deque.")
        )
        assert score.forbidden_hits == ["deque"]
        assert score.faithfulness == 0.5

    def test_forbidden_claim_pattern_counts_and_stacks(self):
        body = "A stack is LIFO. A queue is FIFO. A deque with priority."
        score = offline.score_offline(_case(), _summary(body))
        assert len(score.forbidden_hits) == 2
        assert score.faithfulness == 0.25

    def test_no_facts_falls_back_to_coverage(self):
        case = _case(required_facts=[])
        assert offline.score_offline(case, _summary("only LIFO")).fact_recall == 0.5

    def test_connection_violation_breaks_structure_ok(self):
        body = "A stack is LIFO. A queue is FIFO."
        text = _summary(body).replace(
            f"## Connections\n\n{body}", "## Connections\n\nBuilds on Week 1."
        )
        score = offline.score_offline(_case(), text)
        assert not score.structure_ok
        assert score.connection_violations


class TestGate:
    @pytest.fixture
    def baseline(self):
        return {
            "threshold": 0.02,
            "aggregate": {"faithfulness": 1.0},
            "cases": {"c": {}},
        }

    def _run(self, tmp_path, text, case=None):
        (tmp_path / "c.md").write_text(text)
        return offline.run_offline([case or _case()], tmp_path)

    def test_faithful_fixture_passes(self, tmp_path, baseline):
        run = self._run(tmp_path, _summary())
        assert offline.check_against_baseline(run, baseline) == []

    def test_unfaithful_fixture_fails_the_gate(self, tmp_path, baseline):
        """The deliberately unfaithful fixture: it names outside material."""
        run = self._run(tmp_path, _summary("A stack is LIFO. A queue is FIFO. A deque."))
        failures = offline.check_against_baseline(run, baseline)
        assert any("aggregate faithfulness" in f for f in failures)

    def test_dropped_facts_fail_the_gate(self, tmp_path, baseline):
        run = self._run(tmp_path, _summary("A stack is LIFO."))
        assert offline.check_against_baseline(run, baseline)

    def test_drop_within_threshold_passes(self, tmp_path):
        cases = [_case(id=f"c{i}") for i in range(100)]
        for i in range(len(cases)):
            body = "A stack is LIFO." if i == 0 else "A stack is LIFO. A queue is FIFO."
            (tmp_path / f"c{i}.md").write_text(_summary(body))
        run = offline.run_offline(cases, tmp_path)
        baseline = {
            "threshold": 0.02,
            "aggregate": {"faithfulness": 1.0},
            "cases": {c["id"]: {} for c in cases},
        }
        assert run.faithfulness == pytest.approx(0.995)
        assert offline.check_against_baseline(run, baseline) == []

    def test_new_structure_break_fails_even_when_faithful(self, tmp_path, baseline):
        baseline["cases"] = {"c": {"structure_ok": True}}
        run = self._run(tmp_path, _summary(drop=("Key Takeaways",)))
        failures = offline.check_against_baseline(run, baseline)
        assert any("structure broke" in f and "Key Takeaways" in f for f in failures)

    def test_structure_break_unknown_to_baseline_fails(self, tmp_path, baseline):
        run = self._run(tmp_path, _summary(drop=("Key Takeaways",)))
        assert any("structure broke" in f for f in offline.check_against_baseline(run, baseline))

    def test_baseline_known_structure_break_is_a_warning_not_a_failure(self, tmp_path, baseline):
        baseline["cases"] = {"c": {"structure_ok": False}}
        run = self._run(tmp_path, _summary(drop=("Key Takeaways",)))
        assert offline.check_against_baseline(run, baseline) == []
        assert offline.known_broken(run, baseline) == ["c"]
        report = offline.format_offline_report(run, baseline, [])
        assert "WARN: c" in report
        assert "RESULT: PASS" in report

    def test_baseline_case_without_a_case_file_is_stale(self, tmp_path, baseline):
        baseline["cases"]["gone"] = {"structure_ok": True}
        run = self._run(tmp_path, _summary())
        failures = offline.check_against_baseline(run, baseline)
        assert any("gone" in f and "stale" in f for f in failures)
        assert offline.check_against_baseline(run, baseline, expect_all_cases=False) == []

    def test_missing_fixture_fails(self, tmp_path, baseline):
        run = offline.run_offline([_case()], tmp_path)
        assert run.missing_fixtures == ["c"]
        assert any("no stored summary" in f for f in offline.check_against_baseline(run, baseline))

    def test_case_absent_from_baseline_fails(self, tmp_path, baseline):
        baseline["cases"] = {}
        run = self._run(tmp_path, _summary())
        assert any("not in baseline" in f for f in offline.check_against_baseline(run, baseline))

    def test_missing_baseline_file_is_an_error(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            offline.load_baseline(tmp_path / "nope.json")


class TestCommittedSuite:
    """The committed cases, fixtures and baseline must agree with each other."""

    def test_at_least_twenty_cases(self):
        assert len(CASES) >= 20

    def test_lecture_shapes_are_covered(self):
        shapes = {c.get("shape") for c in CASES}
        assert {
            "sparse_slides",
            "code_heavy",
            "formula_heavy",
            "diagram_heavy",
            "short",
            "long",
            "two_files",
        } <= shapes

    def test_two_file_cases_really_have_two_files(self):
        for case in CASES:
            if case.get("shape") == "two_files":
                assert len({p.get("file") for p in case["pages"]}) >= 2, case["id"]

    @pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
    def test_case_is_well_formed(self, case):
        source = " ".join(p["text"] for p in case["pages"])
        assert case["required_facts"], "no required facts"
        assert case["forbidden_claims"] or case["must_not_mention"]
        for fact in case["required_facts"]:
            for term in fact.get("all", []):
                assert scoring._mentions(source, term), f"{fact['fact']}: {term!r} not in source"
            # `any` lists are phrasings of one fact ("accepts" / "accepted"): the
            # lecture need only contain one of them, the others are for the summary.
            alternatives = fact.get("any", [])
            if alternatives:
                assert any(scoring._mentions(source, t) for t in alternatives), (
                    f"{fact['fact']}: none of {alternatives!r} in source"
                )
        for claim in case["forbidden_claims"]:
            import re

            assert not re.search(claim["pattern"], source, re.IGNORECASE | re.DOTALL), (
                f"forbidden claim {claim['claim']!r} matches the source itself"
            )

    @pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
    def test_stored_fixture_matches_its_baseline_entry(self, case):
        """Fixtures are real model output, so they are imperfect; they must equal the baseline."""
        text = (offline.FIXTURES_DIR / f"{case['id']}.md").read_text()
        score = offline.score_offline(case, text)
        assert score.to_baseline() == offline.load_baseline()["cases"][case["id"]]

    def test_baseline_records_where_the_fixtures_came_from(self):
        provenance = offline.load_baseline()["provenance"]
        assert provenance["source"] == "live"
        assert provenance["model"]
        assert provenance["date"]

    def test_committed_gate_passes(self):
        run = offline.run_offline(CASES)
        assert offline.check_against_baseline(run, offline.load_baseline()) == []

    def test_baseline_covers_exactly_the_cases(self):
        baseline = offline.load_baseline()
        assert set(baseline["cases"]) == {c["id"] for c in CASES}


class TestCli:
    def test_check_passes_on_the_committed_suite(self, capsys):
        assert cli.main(["--offline", "--check"]) == 0
        assert "RESULT: PASS" in capsys.readouterr().out

    def test_check_fails_on_an_unfaithful_fixture_directory(self, tmp_path, capsys):
        for case in CASES:
            text = (offline.FIXTURES_DIR / f"{case['id']}.md").read_text()
            if case["id"] == "deadlock":
                text += "\nIt also covers the banker's algorithm and livelock.\n"
            (tmp_path / f"{case['id']}.md").write_text(text)
        code = cli.main(["--offline", "--check", "--fixtures", str(tmp_path)])
        out = capsys.readouterr().out
        assert code == 1
        assert "RESULT: FAIL" in out
        assert "forbidden claim" in out

    def test_check_fails_when_a_fixture_is_missing(self, tmp_path, capsys):
        assert cli.main(["--offline", "--check", "--fixtures", str(tmp_path)]) == 1
        assert "no stored summary fixture" in capsys.readouterr().out

    def test_write_baseline_refuses_when_fixtures_are_missing(self, tmp_path):
        with patch.object(cli, "BASELINE_PATH", tmp_path / "b.json"):
            assert cli.main(["--offline", "--write-baseline", "--fixtures", str(tmp_path)]) == 1
        assert not (tmp_path / "b.json").exists()

    def test_write_baseline_round_trips(self, tmp_path):
        target = tmp_path / "b.json"
        with patch.object(cli, "BASELINE_PATH", target):
            assert cli.main(["--offline", "--write-baseline"]) == 0
        data = json.loads(target.read_text())
        assert data["aggregate"]["cases"] == len(CASES)

    def test_live_rejects_offline_only_flags(self):
        with pytest.raises(SystemExit):
            cli.main(["--live", "--check"])

    def test_a_mode_is_required(self):
        with pytest.raises(SystemExit):
            cli.main([])

    def test_offline_never_asks_for_an_agent(self):
        with patch("app.agents.factory.get_agent", side_effect=AssertionError("AI call")):
            assert cli.main(["--offline", "--check"]) == 0


class TestLiveSavesFixtures:
    def test_live_run_stores_the_first_summary_per_case(self, tmp_path):
        class FakeAgent:
            usage = SimpleNamespace(calls=1, input_tokens=1, output_tokens=1)

            def reset_usage(self):
                pass

            async def generate_summary(self, extraction, other_weeks):
                return SimpleNamespace(content_md=_summary())

        with patch("app.agents.factory.get_agent", return_value=FakeAgent()):
            asyncio.run(runner.run(only="deadlock", judge=False, save_summaries_to=tmp_path))

        assert (tmp_path / "deadlock.md").read_text().startswith("# CSIT101")
