"""Cost guards (COST-01): bounded top_k and non-zero default ceilings."""

import pytest
from pydantic import ValidationError

from app.api.schemas import MAX_TOP_K, QARequest
from app.config import Settings


class TestTopKBound:
    def test_accepts_the_maximum(self):
        assert QARequest(question="q", top_k=MAX_TOP_K).top_k == MAX_TOP_K

    @pytest.mark.parametrize("bad", [0, -1, MAX_TOP_K + 1, 10_000_000])
    def test_rejects_out_of_range(self, bad):
        with pytest.raises(ValidationError):
            QARequest(question="q", top_k=bad)

    def test_none_still_allowed(self):
        assert QARequest(question="q").top_k is None


class TestCeilingDefaults:
    def test_global_ceilings_are_on_by_default(self):
        # The model default, not an instance: the suite pins the env to 0.
        fields = Settings.model_fields
        assert fields["global_max_ai_calls_per_day"].default > 0
        assert fields["global_max_ai_tokens_per_day"].default > 0
