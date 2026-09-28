"""Tests for the summary eval harness.

A scorer that is wrong makes every eval it runs worthless — worse than no eval,
because the numbers look like evidence. These check the scorer, and they check
the hand-written cases, which are the other thing that can quietly be wrong.
"""

import json
from unittest.mock import patch

import pytest
from evals import runner, scoring


def _summary(sections: list[str] | None = None, body: str = "") -> str:
    """A summary with the required sections, so structure never masks the point."""
    heads = sections if sections is not None else scoring.required_sections()
    return "\n\n".join(f"## {h}\n\n{body}" for h in heads)


class TestMentions:
    def test_is_case_insensitive(self):
        assert scoring._mentions("Discusses Functional Dependency here", "functional dependency")

    def test_ignores_hyphen_and_space_spelling(self):
        """The same term attracts all three spellings in prose."""
        assert scoring._mentions("covers Boyce-Codd normal form", "Boyce Codd")
        assert scoring._mentions("covers Boyce Codd normal form", "Boyce-Codd")

    def test_matches_inside_a_word_boundary_free_context(self):
        assert scoring._mentions("the 3NF rule", "3NF")

    def test_does_not_match_an_absent_term(self):
        assert not scoring._mentions("covers 1NF and 2NF", "3NF")


class TestDeterministicScoring:
    def test_full_coverage_and_clean_structure_passes(self):
        case = {"id": "c", "must_mention": ["1NF", "3NF"], "must_not_mention": ["BCNF"]}

        score = scoring.score_deterministic(case, _summary(body="covers 1NF and 3NF"))

        assert score.coverage == 1.0
        assert score.passed

    def test_a_missing_concept_lowers_coverage_and_is_named(self):
        case = {"id": "c", "must_mention": ["1NF", "2NF", "3NF"]}

        score = scoring.score_deterministic(case, _summary(body="covers 1NF and 2NF"))

        assert score.coverage == pytest.approx(2 / 3)
        assert score.missing == ["3NF"]
        assert not score.passed

    def test_a_fabricated_concept_fails_even_at_full_coverage(self):
        """The finding that matters most.

        Every expected concept is present, so coverage is perfect — and the
        summary still told a student their lecture covered BCNF when it never
        mentioned it. A coverage-only score would call this a pass.
        """
        case = {"id": "c", "must_mention": ["3NF"], "must_not_mention": ["BCNF"]}

        score = scoring.score_deterministic(case, _summary(body="covers 3NF and BCNF"))

        assert score.coverage == 1.0
        assert score.fabricated == ["BCNF"]
        assert not score.passed

    def test_a_missing_section_fails(self):
        case = {"id": "c", "must_mention": ["3NF"]}
        truncated = _summary(sections=scoring.required_sections()[:2], body="covers 3NF")

        score = scoring.score_deterministic(case, truncated)

        assert score.missing_sections
        assert not score.passed

    def test_a_case_with_no_expectations_is_full_coverage_not_a_crash(self):
        score = scoring.score_deterministic({"id": "c"}, _summary())

        assert score.coverage == 1.0

    def test_faithfulness_does_not_decide_pass(self):
        """It is a model's opinion, so gating on it would make the result
        depend on which backend happened to judge."""
        case = {"id": "c", "must_mention": ["3NF"]}
        score = scoring.score_deterministic(case, _summary(body="covers 3NF"))
        score.faithfulness = 1

        assert score.passed


class TestRequiredSections:
    def test_derived_from_the_prompt_not_hardcoded(self):
        """Editing the prompt must not leave this checking a stale format.

        The golden suite makes the same derivation for the same reason; if the
        two ever disagree, one of them is asserting a format that no longer
        exists.
        """
        sections = scoring.required_sections()

        assert "Overview" in sections
        assert "Key Concepts" in sections
        assert len(sections) >= 6


class TestJudgeReplyParsing:
    def test_the_line_format_the_judge_is_asked_for(self):
        """The primary format. It is line-oriented rather than JSON because the
        judge rides on `answer_question`, whose adapters parse the reply as
        `{"answer", "citations"}` and return only the answer string — a bare
        JSON verdict was swallowed whole and came back empty."""
        score, unsupported, error = scoring.parse_judge_reply(
            "FAITHFULNESS: 3\nUNSUPPORTED: claims BCNF\nUNSUPPORTED: claims 4NF"
        )

        assert (score, unsupported, error) == (3, ["claims BCNF", "claims 4NF"], None)

    def test_a_clean_verdict_has_no_claims(self):
        score, unsupported, error = scoring.parse_judge_reply("FAITHFULNESS: 5")

        assert (score, unsupported, error) == (5, [], None)

    def test_a_none_placeholder_is_not_a_claim(self):
        _, unsupported, _ = scoring.parse_judge_reply("FAITHFULNESS: 5\nUNSUPPORTED: none")

        assert unsupported == []

    def test_an_empty_reply_is_named_as_such(self):
        """The failure that actually happened, three times, while being paid for."""
        score, _, error = scoring.parse_judge_reply("")

        assert score is None
        assert error and "empty" in error

    def test_plain_json(self):
        score, unsupported, error = scoring.parse_judge_reply(
            '{"faithfulness": 4, "unsupported": ["claims BCNF"]}'
        )

        assert (score, unsupported, error) == (4, ["claims BCNF"], None)

    def test_json_wrapped_in_prose_and_a_fence(self):
        """Models wrap their output however the mood takes them."""
        score, _, error = scoring.parse_judge_reply(
            'Here is my assessment:\n```json\n{"faithfulness": 5, "unsupported": []}\n```\nHope that helps.'
        )

        assert score == 5
        assert error is None

    def test_an_unparseable_reply_is_an_error_not_a_zero(self):
        """A reply that cannot be read says nothing about the summary.

        Scoring it zero would look like a damning verdict on the output when it
        is actually a broken judge.
        """
        score, _, error = scoring.parse_judge_reply("I could not complete that request.")

        assert score is None
        assert error and "no verdict" in error

    def test_malformed_json_is_reported(self):
        score, _, error = scoring.parse_judge_reply('{"faithfulness": 4,,}')

        assert score is None
        assert error

    def test_an_out_of_range_score_is_refused(self):
        score, _, error = scoring.parse_judge_reply('{"faithfulness": 11}')

        assert score is None
        assert error and "out-of-range" in error

    def test_a_non_integer_score_is_refused(self):
        score, _, error = scoring.parse_judge_reply('{"faithfulness": "good"}')

        assert score is None
        assert error

    def test_a_string_instead_of_a_list_is_tolerated(self):
        _, unsupported, error = scoring.parse_judge_reply(
            '{"faithfulness": 3, "unsupported": "claims BCNF"}'
        )

        assert unsupported == ["claims BCNF"]
        assert error is None


class TestTheCasesThemselves:
    """The expectations are hand-written, so they are the other thing that can
    quietly be wrong — and a broken case produces a confident wrong number."""

    @pytest.fixture(scope="class")
    def cases(self):
        return runner.load_cases()

    def test_there_are_cases(self, cases):
        assert cases

    def test_every_case_has_the_required_fields(self, cases):
        for case in cases:
            assert case["id"]
            assert case["pages"]
            assert case["must_mention"], f"{case['id']} asserts nothing"

    def test_ids_are_unique(self, cases):
        ids = [c["id"] for c in cases]
        assert len(ids) == len(set(ids))

    def test_every_expected_concept_is_actually_in_the_source(self, cases):
        """Otherwise the expectation is impossible and the case always fails.

        This is the check that catches a typo in a `must_mention` term, which
        would otherwise read as the model missing something it was never given.
        """
        for case in cases:
            source = " ".join(p["text"] for p in case["pages"])
            missing = [t for t in case["must_mention"] if not scoring._mentions(source, t)]
            assert not missing, f"{case['id']}: not in its own source: {missing}"

    def test_no_fabrication_term_appears_in_the_source(self, cases):
        """Otherwise it is not a fabrication — it is a concept the lecture
        covered, and flagging it would be the harness inventing a failure."""
        for case in cases:
            source = " ".join(p["text"] for p in case["pages"])
            present = [t for t in case["must_not_mention"] if scoring._mentions(source, t)]
            assert not present, f"{case['id']}: must_not_mention is in the source: {present}"

    def test_fabrication_terms_are_plausible_for_the_topic(self, cases):
        """Each case needs some, or it tests nothing about hallucination.

        A trip-wire only works if the term is one a model might reach for —
        which is why these are the real adjacent topics, not nonsense strings.
        """
        for case in cases:
            assert case["must_not_mention"], f"{case['id']} has no fabrication trip-wires"

    def test_every_case_records_why_it_was_written(self, cases):
        """The reasoning is the part a later reader cannot reconstruct."""
        for case in cases:
            assert case.get("notes"), f"{case['id']} has no notes"

    def test_cases_are_valid_json_on_disk(self):
        for path in runner.CASES_DIR.glob("*.json"):
            json.loads(path.read_text())


class TestLoadCases:
    def test_can_narrow_to_one(self):
        cases = runner.load_cases(only="normalisation")

        assert len(cases) == 1
        assert cases[0]["id"] == "normalisation"

    def test_an_unknown_id_is_an_error_not_an_empty_run(self):
        """An empty run would report 0/0 passed, which reads as success."""
        with pytest.raises(ValueError, match="No eval case"):
            runner.load_cases(only="does-not-exist")


class TestReport:
    def _aggregate(self, case_id, runs):
        return runner.CaseAggregate(case_id=case_id, runs=runs)

    def _score(self, coverage=1.0, fabricated=None, calls=1, tokens=(100, 50)):
        return scoring.CaseScore(
            case_id="x",
            coverage=coverage,
            fabricated=fabricated or [],
            calls=calls,
            input_tokens=tokens[0],
            output_tokens=tokens[1],
        )

    def test_aggregates_pass_count_and_coverage(self):
        report = runner.RunReport(backend="zai")
        report.cases = [
            self._aggregate("a", [self._score()]),
            self._aggregate("b", [self._score(coverage=0.5)]),
        ]

        assert report.passed == 1
        assert report.coverage == 0.75

    def test_totals_the_cost(self):
        """Now that metering exists, an eval run reports what it spent."""
        report = runner.RunReport(backend="zai")
        report.cases = [self._aggregate("a", [self._score(), self._score()])]

        assert report.total_calls == 2
        assert report.total_tokens == 300

    def test_an_empty_report_does_not_divide_by_zero(self):
        assert runner.RunReport(backend="zai").coverage == 0.0

    def test_the_formatted_report_names_persistent_fabrications_loudly(self):
        report = runner.RunReport(backend="zai")
        report.cases = [self._aggregate("a", [self._score(fabricated=["BCNF"])])]

        text = runner.format_report(report)

        assert "FABRICATED every run" in text
        assert "BCNF" in text

    def test_the_json_report_round_trips(self):
        report = runner.RunReport(backend="zai")
        report.cases = [self._aggregate("a", [self._score()])]

        assert json.loads(json.dumps(report.to_dict()))["backend"] == "zai"


class TestRepeatedRuns:
    """`-n` exists because one run is a sample, not a verdict.

    The first live run of this harness found four fabrications on
    `normalisation`; a later run of the same case found one. Reporting either
    number alone invites acting on noise.
    """

    def _agg(self, *fabrication_lists, coverage=1.0):
        runs = [
            scoring.CaseScore(case_id="a", coverage=coverage, fabricated=list(f))
            for f in fabrication_lists
        ]
        return runner.CaseAggregate(case_id="a", runs=runs)

    def test_a_fabrication_in_every_run_is_persistent(self):
        """A property of the prompt, and worth fixing."""
        agg = self._agg(["BCNF"], ["BCNF"], ["BCNF"])

        assert agg.persistent_fabrications == ["BCNF"]
        assert agg.occasional_fabrications == []

    def test_a_fabrication_in_some_runs_is_occasional(self):
        """Real, but not reliably reproducible — a different call to make."""
        agg = self._agg(["BCNF"], [], ["BCNF"])

        assert agg.persistent_fabrications == []
        assert agg.occasional_fabrications == [("BCNF", 2)]

    def test_frequency_is_reported_per_term(self):
        agg = self._agg(["BCNF", "4NF"], ["BCNF"], ["BCNF", "5NF"])

        assert agg.fabrication_frequency == {"BCNF": 3, "4NF": 1, "5NF": 1}

    def test_a_case_passes_only_if_every_run_did(self):
        """Passing sometimes is not passing."""
        agg = self._agg([], ["BCNF"], [])

        assert agg.passed_runs == 2
        assert not agg.passed

    def test_disagreeing_runs_are_flagged_unstable(self):
        """An unstable case means the number is not repeatable, so comparing it
        against a previous run tells you nothing — a different problem from
        failing, and reported separately."""
        agg = self._agg([], ["BCNF"])

        assert not agg.stable

    def test_runs_that_all_agree_are_stable_whether_passing_or_failing(self):
        assert self._agg([], []).stable
        assert self._agg(["BCNF"], ["BCNF"]).stable

    def test_the_report_names_unstable_cases(self):
        report = runner.RunReport(backend="zai", n=2)
        report.cases = [self._agg([], ["BCNF"])]

        text = runner.format_report(report)

        assert "UNSTABLE" in text
        assert "1/2 runs" in text

    def test_faithfulness_is_averaged_across_runs(self):
        agg = self._agg([], [])
        agg.runs[0].faithfulness = 4
        agg.runs[1].faithfulness = 2

        assert agg.mean_faithfulness == 3.0

    def test_faithfulness_is_none_when_the_judge_never_answered(self):
        assert self._agg([], []).mean_faithfulness is None


class _StubAgent:
    """An adapter that returns a summary chosen by the test.

    Lets the whole path — runner to agent to scorer to report — be exercised
    with no credentials and no cost, which is the only way this wiring gets
    tested at all: a real run needs a backend and money.
    """

    def __init__(self, summary: str, judge_reply: str | None = None):
        from app.agents.base import TokenUsage

        self._summary = summary
        self._judge_reply = judge_reply
        self.usage = TokenUsage()
        self.judged = False
        self.judge_chunks = None

    def reset_usage(self):
        from app.agents.base import TokenUsage

        self.usage = TokenUsage()

    async def generate_summary(self, extraction, existing_summary):
        from app.agents.base import SummaryResult

        self.usage.add(input_tokens=1000, output_tokens=500)
        return SummaryResult(content_md=self._summary)

    async def answer_question(self, question, context_chunks):
        from app.agents.base import AnswerResult

        self.judged = True
        self.judge_chunks = context_chunks
        if self._judge_reply is None:
            raise RuntimeError("judge unavailable")
        self.usage.add(input_tokens=200, output_tokens=40)
        return AnswerResult(answer=self._judge_reply)


@pytest.mark.asyncio
class TestRunnerEndToEnd:
    async def _run(self, summary, judge_reply=None, judge=True):
        agent = _StubAgent(summary, judge_reply)
        with patch("app.agents.factory.get_agent", return_value=agent):
            report = await runner.run(only="normalisation", judge=judge)
        return report, agent

    async def test_a_good_summary_passes_and_reports_cost(self):
        case = runner.load_cases(only="normalisation")[0]
        body = " ".join(case["must_mention"])

        report, _ = await self._run(
            _summary(body=body), judge_reply='{"faithfulness": 5, "unsupported": []}'
        )

        assert report.passed == 1
        assert report.cases[0].runs[0].faithfulness == 5
        # Summary call plus judge call, with the tokens the metering reported.
        assert report.total_calls == 2
        assert report.total_tokens == 1740

    async def test_a_fabrication_fails_the_case(self):
        case = runner.load_cases(only="normalisation")[0]
        body = " ".join(case["must_mention"]) + " and also BCNF"

        report, _ = await self._run(
            _summary(body=body), judge_reply='{"faithfulness": 2, "unsupported": ["BCNF"]}'
        )

        assert report.passed == 0
        assert "BCNF" in report.cases[0].persistent_fabrications

    async def test_a_judge_failure_does_not_lose_the_deterministic_result(self):
        """The free half of the eval is worth reporting even when the paid half
        is unavailable — otherwise a missing key discards findings that cost
        nothing to produce."""
        case = runner.load_cases(only="normalisation")[0]
        body = " ".join(case["must_mention"])

        report, _ = await self._run(_summary(body=body), judge_reply=None)

        assert report.passed == 1
        assert report.cases[0].runs[0].faithfulness is None
        assert "judge unavailable" in report.cases[0].runs[0].judge_error

    async def test_no_judge_skips_the_second_call_entirely(self):
        """`--no-judge` is what makes this runnable with no credentials."""
        case = runner.load_cases(only="normalisation")[0]
        body = " ".join(case["must_mention"])

        report, agent = await self._run(_summary(body=body), judge=False)

        assert agent.judged is False
        assert report.total_calls == 1

    async def test_the_judge_actually_receives_the_source_and_summary(self):
        """The contract `prompts/answer_question.txt` renders, pinned.

        The template reads `chunk.text`; an earlier version of the runner passed
        `content`, so every chunk rendered blank and the judge replied that it
        had been handed "empty placeholders". It graded nothing on three cases
        and the failure surfaced only as a parse error — the harness reported
        "judge unavailable" and looked like a flaky model.

        Every other test here passed against that bug, because none of them
        looked at what the judge was given.
        """
        case = runner.load_cases(only="normalisation")[0]
        summary = _summary(body="covers " + " ".join(case["must_mention"]))

        _, agent = await self._run(summary, judge_reply='{"faithfulness": 5}')

        chunks = agent.judge_chunks
        assert len(chunks) == 2
        for chunk in chunks:
            assert chunk.get("text"), "chunk rendered blank — wrong field name"
        # The source has to be the lecture, not the summary echoed back.
        assert case["pages"][0]["text"][:40] in chunks[0]["text"]
        assert summary[:40] in chunks[1]["text"]
