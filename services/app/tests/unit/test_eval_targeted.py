"""Tests for the offline targeted-generation eval and its CI gate."""

import copy
import json
from unittest.mock import patch

import pytest
from evals import __main__ as cli
from evals import targeted

CASES = targeted.load_targeted_cases()


def _case(**kw) -> dict:
    base = {
        "id": "c",
        "source_case": "hash_tables",
        "kind": "quiz",
        "count": 5,
        "weak_topics": [{"label": "Load factor", "terms": ["load factor", "rehash"]}],
        "existing": ["What is the load factor of a hash table?"],
    }
    base.update(kw)
    return base


def _quiz(question: str, page: int, expect: str | None = "keep", answer: str = "x") -> dict:
    item = {
        "question_type": "short_answer",
        "question": question,
        "options": None,
        "correct_answer": answer,
        "explanation": "",
        "source_page_ref": page,
    }
    if expect:
        item["expect"] = expect
    return item


def _score(items: list[dict], **case_kw) -> targeted.TargetedScore:
    return targeted.score_targeted(_case(**case_kw), {"kind": "quiz", "items": items})


class TestCommittedCases:
    def test_there_are_at_least_ten_cases_with_both_kinds(self):
        assert len(CASES) >= 10
        assert {c["kind"] for c in CASES} == {"quiz", "flashcards"}

    def test_every_case_has_a_fixture_and_a_source_lecture(self):
        for case in CASES:
            assert (targeted.FIXTURES_DIR / f"{case['id']}.json").is_file(), case["id"]
            assert targeted.lecture_pages(case), case["id"]

    def test_the_committed_baseline_agrees_with_the_fixtures(self):
        run = targeted.run_targeted_offline(CASES)
        baseline = targeted.load_targeted_baseline()
        assert targeted.check_targeted(run, baseline) == []

    def test_the_bars_hold_on_the_committed_fixtures(self):
        run = targeted.run_targeted_offline(CASES)
        assert run.on_topic >= 0.8
        assert run.citation_validity >= 0.95
        assert run.dedup >= 0.95

    def test_the_baseline_records_the_live_run(self):
        provenance = targeted.load_targeted_baseline()["provenance"]
        assert provenance == {
            "source": "live",
            "model": "glm-5.3-flash",
            "date": "2026-10-15",
            "prompt": "generate_targeted v1.0",
        }


class TestScoring:
    def test_planted_duplicate_and_uncited_are_dropped(self):
        score = _score(
            [
                _quiz("What happens when the load factor crosses a threshold?", 3),
                _quiz("What is the load factor of a hash table", 1, "duplicate"),
                _quiz("What is a Bloom filter?", 99, "uncited"),
            ]
        )
        assert (score.kept, score.dropped_duplicate, score.dropped_uncited) == (1, 1, 1)
        assert score.dedup == 1.0 and score.filter_accuracy == 1.0
        assert score.citation_validity == 1.0 and score.on_topic == 1.0

    def test_an_undetected_duplicate_lowers_dedup(self):
        score = _score(
            [_quiz("Explain how rehash cost is shared across insertions.", 3, "duplicate")],
            existing=["Explain how the cost of a rehash is amortised."],
        )
        assert score.dedup == 0.0 and score.problems

    def test_a_page_that_does_not_support_the_item_is_invalid(self):
        # Page 1 never mentions rehashing.
        score = _score([_quiz("What does a rehash do to every key?", 1)])
        assert score.citation_validity == 0.0
        assert any("does not support" in p for p in score.problems)

    def test_an_off_topic_item_is_reported(self):
        score = _score([_quiz("What is a linked list?", 2)])
        assert score.on_topic == 0.0 and any("off topic" in p for p in score.problems)

    def test_nothing_kept_scores_zero_not_one(self):
        score = _score([_quiz("What is a Bloom filter?", 99, "uncited")])
        assert score.kept == 0 and score.on_topic == 0.0 and score.citation_validity == 0.0

    def test_unlabelled_items_are_scored_without_expectations(self):
        score = _score([_quiz("What is the load factor threshold for rehash?", 3, expect=None)])
        assert score.kept == 1 and score.dedup == 1.0 and score.filter_accuracy == 1.0

    def test_flashcards_use_front_and_back(self):
        card = {
            "front": "What triggers a rehash?",
            "back": "The load factor.",
            "tags": ["load"],
            "source_page_ref": 3,
            "expect": "keep",
        }
        score = targeted.score_targeted(
            _case(kind="flashcards"), {"kind": "flashcards", "items": [card]}
        )
        assert score.kept == 1 and score.on_topic == 1.0


class TestGate:
    def _baseline(self) -> dict:
        return targeted.load_targeted_baseline()

    def _fixtures(self, tmp_path, mutate=None):
        for case in CASES:
            data = json.loads((targeted.FIXTURES_DIR / f"{case['id']}.json").read_text())
            if mutate and case["id"] == CASES[0]["id"]:
                data = mutate(copy.deepcopy(data))
            (tmp_path / f"{case['id']}.json").write_text(json.dumps(data))
        return tmp_path

    def test_a_missing_fixture_fails(self, tmp_path):
        run = targeted.run_targeted_offline(CASES, tmp_path)
        failures = targeted.check_targeted(run, self._baseline())
        assert any("no stored targeted fixture" in f for f in failures)

    def test_unsupporting_citations_across_the_set_fail_the_bar(self, tmp_path):
        def break_citation(data):
            for item in data["items"]:
                item["source_page_ref"] = 1 if item["source_page_ref"] != 1 else 2
            return data

        for case in CASES:
            data = json.loads((targeted.FIXTURES_DIR / f"{case['id']}.json").read_text())
            (tmp_path / f"{case['id']}.json").write_text(json.dumps(break_citation(data)))
        run = targeted.run_targeted_offline(CASES, tmp_path)
        failures = targeted.check_targeted(run, self._baseline())
        assert any("citation validity" in f for f in failures)

    @staticmethod
    def _run_with_citation(validity: float) -> targeted.TargetedRun:
        score = targeted.TargetedScore(
            case_id="c",
            kind="quiz",
            total=5,
            kept=5,
            dropped_uncited=0,
            dropped_duplicate=0,
            on_topic=1.0,
            citation_validity=validity,
            dedup=1.0,
            filter_accuracy=1.0,
        )
        return targeted.TargetedRun(scores=[score])

    @staticmethod
    def _baseline_at(validity: float) -> dict:
        return {
            "aggregate": {
                "on_topic": 1.0,
                "citation_validity": validity,
                "dedup": 1.0,
                "filter_accuracy": 1.0,
            },
            "cases": {"c": {}},
        }

    def test_citation_validity_below_the_bar_fails(self):
        assert targeted.CITATION_FLOOR == 0.95
        run = self._run_with_citation(0.94)
        failures = targeted.check_targeted(run, self._baseline_at(0.94))
        assert any("citation validity" in f for f in failures)

    def test_citation_validity_at_the_bar_passes(self):
        run = self._run_with_citation(0.95)
        assert targeted.check_targeted(run, self._baseline_at(0.95)) == []

    def test_a_citation_regression_against_the_baseline_fails(self):
        run = self._run_with_citation(0.96)
        failures = targeted.check_targeted(run, self._baseline_at(1.0))
        assert any("aggregate citation_validity" in f for f in failures)

    def test_off_topic_output_fails_the_floor(self, tmp_path):
        def off_topic(data):
            for item in data["items"]:
                for key in ("question", "front"):
                    if key in item:
                        item[key] = "Describe your favourite colour."
                for key in ("correct_answer", "back", "explanation"):
                    if key in item:
                        item[key] = "Blue."
            return data

        fixtures = tmp_path
        for case in CASES:
            data = json.loads((targeted.FIXTURES_DIR / f"{case['id']}.json").read_text())
            (fixtures / f"{case['id']}.json").write_text(json.dumps(off_topic(data)))
        run = targeted.run_targeted_offline(CASES, fixtures)
        failures = targeted.check_targeted(run, self._baseline())
        assert any("on-topic" in f for f in failures)

    def test_a_case_missing_from_the_baseline_fails(self):
        run = targeted.run_targeted_offline(CASES)
        baseline = self._baseline()
        del baseline["cases"][CASES[0]["id"]]
        assert any("not in baseline" in f for f in targeted.check_targeted(run, baseline))

    def test_a_stale_baseline_case_fails(self):
        run = targeted.run_targeted_offline(CASES)
        baseline = self._baseline()
        baseline["cases"]["gone"] = {}
        assert any("stale baseline" in f for f in targeted.check_targeted(run, baseline))

    def test_an_aggregate_regression_fails(self):
        run = targeted.run_targeted_offline(CASES)
        baseline = self._baseline()
        baseline["aggregate"]["filter_accuracy"] = 1.5
        assert any("filter_accuracy" in f for f in targeted.check_targeted(run, baseline))


class TestCli:
    def test_targeted_check_passes_on_the_committed_files(self, capsys):
        assert cli.main(["--offline", "--targeted", "--check"]) == 0
        assert "RESULT: PASS" in capsys.readouterr().out

    def test_the_ci_command_runs_the_targeted_gate_too(self, capsys):
        assert cli.main(["--offline", "--check"]) == 0
        out = capsys.readouterr().out
        assert "Targeted generation evals" in out

    def test_a_targeted_failure_fails_the_ci_command(self):
        with patch.object(cli, "check_targeted", return_value=["boom"]):
            assert cli.main(["--offline", "--check"]) == 1

    def test_write_baseline_refuses_when_a_fixture_is_missing(self, tmp_path, capsys):
        assert (
            cli.main(["--offline", "--targeted", "--write-baseline", "--fixtures", str(tmp_path)])
            == 1
        )
        assert "cannot write a baseline" in capsys.readouterr().out

    def test_live_targeted_is_a_mode(self):
        args = cli.build_parser().parse_args(["--live", "--targeted"])
        assert args.targeted and args.live


def test_every_targeted_case_names_an_existing_source_case():
    for case in CASES:
        assert case["source_case"], case["id"]
        assert targeted.lecture_pages(case)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_each_committed_fixture_scores_clean(case):
    generated = json.loads((targeted.FIXTURES_DIR / f"{case['id']}.json").read_text())
    score = targeted.score_targeted(case, generated)
    # A live citation miss is allowed (the aggregate bar is 0.95); a wrong filter
    # outcome against the fixture's own label is not.
    assert score.citation_validity >= 0.8
    assert score.dedup == 1.0
    assert score.filter_accuracy == 1.0
