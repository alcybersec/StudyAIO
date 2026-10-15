"""Pure rules of targeted generation: citation, dedup, topics, target (ADR 0007 Decision 5)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.agents.base import FlashcardData, QuizQuestionData
from app.pipeline.targeted_items import (
    AVOID_LIMIT,
    TOPIC_LIMIT,
    Attempt,
    TargetCandidate,
    build_topics,
    choose_target,
    focus_topic_for,
    item_stem,
    latest_missed,
    select_items,
)

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


def _quiz(question: str, page: int = 1) -> QuizQuestionData:
    return QuizQuestionData(
        question_type="short_answer",
        question=question,
        correct_answer="a",
        explanation="e",
        source_page_ref=page,
    )


def _card(front: str, page: int = 1, tags: list[str] | None = None) -> FlashcardData:
    return FlashcardData(front=front, back="b", tags=tags or [], source_page_ref=page)


class TestItemStem:
    def test_quiz_uses_the_question(self):
        assert item_stem("quiz", _quiz("What is a bucket?")) == "What is a bucket?"

    def test_flashcards_use_the_front(self):
        assert item_stem("flashcards", _card("Define bucket")) == "Define bucket"


class TestSelectItems:
    def test_drops_items_citing_a_page_the_artifact_lacks(self):
        items = [_quiz("What is hashing?", 2), _quiz("What is chaining?", 99)]
        result = select_items("quiz", items, valid_pages={1, 2, 3}, existing=[])
        assert [q.question for q in result.kept] == ["What is hashing?"]
        assert result.dropped_uncited == 1 and result.dropped_duplicate == 0

    def test_a_non_integer_page_is_uncited(self):
        item = _quiz("What is hashing?")
        item.source_page_ref = "n/a"  # type: ignore[assignment]
        result = select_items("quiz", [item], valid_pages={1}, existing=[])
        assert result.kept == [] and result.dropped_uncited == 1

    def test_drops_duplicates_of_existing_items(self):
        result = select_items(
            "flashcards",
            [_card("Define a hash table."), _card("What is a load factor?")],
            valid_pages={1},
            existing=["define a hash table"],
        )
        assert [c.front for c in result.kept] == ["What is a load factor?"]
        assert result.dropped_duplicate == 1

    def test_drops_a_duplicate_of_an_earlier_item_in_the_batch(self):
        result = select_items(
            "quiz",
            [_quiz("What is the load factor?"), _quiz("What is the load factor")],
            valid_pages={1},
            existing=[],
        )
        assert len(result.kept) == 1 and result.dropped_duplicate == 1

    def test_uncited_is_counted_before_duplicate(self):
        result = select_items(
            "quiz",
            [_quiz("What is hashing?", 99)],
            valid_pages={1},
            existing=["What is hashing?"],
        )
        assert result.dropped_uncited == 1 and result.dropped_duplicate == 0

    def test_does_not_mutate_its_inputs(self):
        existing = ["a b c"]
        items = [_quiz("What is hashing?")]
        select_items("quiz", items, valid_pages={1}, existing=existing)
        assert existing == ["a b c"] and len(items) == 1


class TestFocusTopic:
    def test_flashcard_tag_naming_a_topic_wins(self):
        card = _card("anything", tags=["Load factor", "x"])
        assert focus_topic_for("flashcards", card, ["Open addressing", "load factor"]) == (
            "load factor"
        )

    def test_matches_the_topic_in_the_text(self):
        item = _quiz("Why does open addressing suffer from clustering?")
        assert focus_topic_for("quiz", item, ["Load factor", "Open addressing"]) == (
            "Open addressing"
        )

    def test_falls_back_to_the_first_topic(self):
        assert focus_topic_for("quiz", _quiz("Unrelated?"), ["Load factor", "x"]) == "Load factor"

    def test_is_capped_to_the_column_width(self):
        long = "t" * 300
        assert len(focus_topic_for("quiz", _quiz("q"), [long]) or "") == 200

    def test_no_topics_is_none(self):
        assert focus_topic_for("quiz", _quiz("q"), []) is None


class TestBuildTopics:
    def test_titles_first_then_concepts_case_insensitive_dedup(self):
        topics = build_topics(
            ["Open addressing", "open addressing", "Load factor"],
            ["LOAD FACTOR", "Rehashing", "Chaining"],
        )
        assert topics == ["Open addressing", "Load factor", "Rehashing", "Chaining"]

    def test_capped_at_the_limit(self):
        topics = build_topics([f"t{i}" for i in range(10)], ["c"])
        assert len(topics) == TOPIC_LIMIT == 5

    def test_blank_labels_are_ignored(self):
        assert build_topics(["  ", "", "A"], [" "]) == ["A"]

    def test_labels_are_trimmed_and_bounded(self):
        assert build_topics([" " + "x" * 400 + " "], [])[0] == "x" * 200

    def test_avoid_limit_is_the_adr_value(self):
        assert AVOID_LIMIT == 30


def _attempt(qid: str, artifact: str, correct: bool, days_ago: float, page: int = 1) -> Attempt:
    return Attempt(
        question_id=qid,
        artifact_id=artifact,
        stem=f"stem {qid}",
        page_ref=page,
        is_correct=correct,
        created_at=NOW - timedelta(days=days_ago),
    )


class TestLatestMissed:
    def test_only_the_latest_attempt_counts(self):
        attempts = [
            _attempt("q1", "a", False, 5),
            _attempt("q1", "a", True, 1),
            _attempt("q2", "a", True, 6),
            _attempt("q2", "a", False, 2),
        ]
        assert [m.question_id for m in latest_missed(attempts)] == ["q2"]

    def test_newest_miss_first(self):
        attempts = [_attempt("q1", "a", False, 9), _attempt("q2", "a", False, 1)]
        assert [m.question_id for m in latest_missed(attempts)] == ["q2", "q1"]

    def test_empty(self):
        assert latest_missed([]) == []


class TestChooseTarget:
    def test_most_missed_wins(self):
        a = TargetCandidate("a", NOW, 1)
        b = TargetCandidate("b", NOW - timedelta(days=3), 4)
        assert choose_target([a, b]) == b

    def test_tie_goes_to_the_newest_artifact(self):
        old = TargetCandidate("a", NOW - timedelta(days=3), 2)
        new = TargetCandidate("b", NOW, 2)
        assert choose_target([old, new]) == new

    def test_then_by_id(self):
        a = TargetCandidate("a", NOW, 0)
        b = TargetCandidate("b", NOW, 0)
        assert choose_target([a, b]) == b
        assert choose_target([b, a]) == b

    def test_none_when_empty(self):
        assert choose_target([]) is None


@pytest.mark.parametrize("kind", ["quiz", "flashcards"])
def test_selection_counts_add_up(kind):
    maker = _quiz if kind == "quiz" else _card
    items = [maker("alpha beta gamma", 1), maker("alpha beta gamma", 1), maker("delta", 9)]
    result = select_items(kind, items, valid_pages={1}, existing=[])
    assert len(result.kept) + result.dropped_uncited + result.dropped_duplicate == len(items)
