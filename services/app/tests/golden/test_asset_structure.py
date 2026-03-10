"""Golden tests for flashcard and quiz question structures.

Validates that AI-generated study assets conform to expected schemas:
- Flashcards: front, back, tags (list[str]), source_page_ref (int)
- Quiz MCQ: question_type="multiple_choice", 4 options, correct_answer in options
- Quiz short answer: question_type="short_answer", no options, has correct_answer
"""


# ── Flashcard structure validation ───────────────────────────────────


class TestFlashcardStructure:
    """Validate flashcard data structure."""

    def test_flashcard_has_required_fields(self, sample_flashcard_list):
        required_fields = {"front", "back", "tags", "source_page_ref"}
        for i, card in enumerate(sample_flashcard_list):
            assert isinstance(card, dict), f"Flashcard {i} must be a dict"
            missing = required_fields - card.keys()
            assert not missing, f"Flashcard {i} missing fields: {missing}"

    def test_flashcard_front_is_nonempty_string(self, sample_flashcard_list):
        for i, card in enumerate(sample_flashcard_list):
            assert isinstance(card["front"], str), f"Flashcard {i} 'front' must be str"
            assert card["front"].strip(), f"Flashcard {i} 'front' must not be empty"

    def test_flashcard_back_is_nonempty_string(self, sample_flashcard_list):
        for i, card in enumerate(sample_flashcard_list):
            assert isinstance(card["back"], str), f"Flashcard {i} 'back' must be str"
            assert card["back"].strip(), f"Flashcard {i} 'back' must not be empty"

    def test_flashcard_tags_is_list_of_strings(self, sample_flashcard_list):
        for i, card in enumerate(sample_flashcard_list):
            assert isinstance(card["tags"], list), f"Flashcard {i} 'tags' must be a list"
            for j, tag in enumerate(card["tags"]):
                assert isinstance(tag, str), f"Flashcard {i}, tag {j} must be str"

    def test_flashcard_source_page_ref_is_positive_int(self, sample_flashcard_list):
        for i, card in enumerate(sample_flashcard_list):
            assert isinstance(card["source_page_ref"], int), (
                f"Flashcard {i} 'source_page_ref' must be int"
            )
            assert card["source_page_ref"] >= 1, f"Flashcard {i} 'source_page_ref' must be >= 1"

    def test_flashcard_list_nonempty(self, sample_flashcard_list):
        assert len(sample_flashcard_list) > 0, "Must have at least one flashcard"


# ── Quiz question structure validation ───────────────────────────────


class TestQuizQuestionStructure:
    """Validate quiz question data structure."""

    def test_quiz_has_required_fields(self, sample_quiz_list):
        required_fields = {
            "question_type",
            "question",
            "correct_answer",
            "explanation",
            "source_page_ref",
        }
        for i, q in enumerate(sample_quiz_list):
            assert isinstance(q, dict), f"Quiz question {i} must be a dict"
            missing = required_fields - q.keys()
            assert not missing, f"Quiz question {i} missing fields: {missing}"

    def test_quiz_question_type_valid(self, sample_quiz_list):
        valid_types = {"multiple_choice", "short_answer"}
        for i, q in enumerate(sample_quiz_list):
            assert q["question_type"] in valid_types, (
                f"Quiz question {i} type '{q['question_type']}' not in {valid_types}"
            )

    def test_quiz_question_is_nonempty_string(self, sample_quiz_list):
        for i, q in enumerate(sample_quiz_list):
            assert isinstance(q["question"], str)
            assert q["question"].strip(), f"Quiz question {i} 'question' must not be empty"

    def test_quiz_correct_answer_is_nonempty(self, sample_quiz_list):
        for _i, q in enumerate(sample_quiz_list):
            assert isinstance(q["correct_answer"], str)
            assert q["correct_answer"].strip()

    def test_quiz_explanation_is_nonempty(self, sample_quiz_list):
        for _i, q in enumerate(sample_quiz_list):
            assert isinstance(q["explanation"], str)
            assert q["explanation"].strip()

    def test_quiz_source_page_ref_is_positive_int(self, sample_quiz_list):
        for _i, q in enumerate(sample_quiz_list):
            assert isinstance(q["source_page_ref"], int)
            assert q["source_page_ref"] >= 1


class TestQuizMultipleChoice:
    """Validate MCQ-specific structure."""

    def _mcq_questions(self, quiz_list):
        return [q for q in quiz_list if q["question_type"] == "multiple_choice"]

    def test_mcq_has_options(self, sample_quiz_list):
        for q in self._mcq_questions(sample_quiz_list):
            assert q.get("options") is not None, "MCQ must have 'options'"
            assert isinstance(q["options"], list), "MCQ 'options' must be a list"

    def test_mcq_has_four_options(self, sample_quiz_list):
        for q in self._mcq_questions(sample_quiz_list):
            assert len(q["options"]) == 4, (
                f"MCQ must have exactly 4 options, got {len(q['options'])}"
            )

    def test_mcq_options_are_nonempty_strings(self, sample_quiz_list):
        for q in self._mcq_questions(sample_quiz_list):
            for i, opt in enumerate(q["options"]):
                assert isinstance(opt, str), f"Option {i} must be str"
                assert opt.strip(), f"Option {i} must not be empty"

    def test_mcq_correct_answer_in_options(self, sample_quiz_list):
        for q in self._mcq_questions(sample_quiz_list):
            assert q["correct_answer"] in q["options"], (
                f"Correct answer '{q['correct_answer']}' not in options: {q['options']}"
            )

    def test_mcq_options_are_unique(self, sample_quiz_list):
        for q in self._mcq_questions(sample_quiz_list):
            assert len(set(q["options"])) == len(q["options"]), "MCQ options must be unique"


class TestQuizShortAnswer:
    """Validate short answer-specific structure."""

    def _sa_questions(self, quiz_list):
        return [q for q in quiz_list if q["question_type"] == "short_answer"]

    def test_short_answer_no_options(self, sample_quiz_list):
        for q in self._sa_questions(sample_quiz_list):
            assert q.get("options") is None, "Short answer must not have options"

    def test_short_answer_has_model_answer(self, sample_quiz_list):
        for q in self._sa_questions(sample_quiz_list):
            assert len(q["correct_answer"]) > 10, (
                "Short answer 'correct_answer' should be a substantive model answer"
            )


class TestQuizMixOfTypes:
    """Validate that the quiz contains a mix of question types."""

    def test_has_multiple_choice(self, sample_quiz_list):
        types = {q["question_type"] for q in sample_quiz_list}
        assert "multiple_choice" in types

    def test_has_short_answer(self, sample_quiz_list):
        types = {q["question_type"] for q in sample_quiz_list}
        assert "short_answer" in types
