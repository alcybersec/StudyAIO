"""Z.ai (GLM) adapter.

Z.ai exposes an OpenAI-compatible Chat Completions API, so this reuses
`OpenAIAdapter` wholesale and only changes where the requests go. Everything
the adapter does — classification, summaries, flashcards, quizzes, Q&A,
streaming, CourseOps, concept extraction — is inherited unchanged.

Docs: https://docs.z.ai/guides/llm/glm-4.6
"""

import structlog

from app.agents.openai_adapter import OpenAIAdapter
from app.services.settings_service import get_effective_setting

logger = structlog.get_logger()

#: Z.ai's OpenAI-compatible endpoint. The SDK appends /chat/completions.
ZAI_BASE_URL = "https://api.z.ai/api/paas/v4/"

#: Current flagship. Overridable per user in Settings > AI Providers.
ZAI_DEFAULT_MODEL = "glm-5.3"


class ZaiAdapter(OpenAIAdapter):
    """Calls Z.ai's GLM models through their OpenAI-compatible endpoint."""

    provider_name = "Z.ai"

    def __init__(self, api_key: str = "", model: str = "", base_url: str = "", thinking: str = ""):
        """Configure the adapter.

        Args:
            api_key: Z.ai API key. Falls back to the `zai_api_key` setting.
            model: GLM model id. Falls back to `zai_model`, then the default.
            base_url: Override the endpoint. Falls back to `zai_base_url`,
                then Z.ai's public endpoint — self-hosted GLM deployments and
                regional endpoints exist, so this stays configurable.
            thinking: GLM thinking mode, "disabled" or "enabled". Falls back
                to the `zai_thinking` setting, then "disabled".

                Measured against the real summarize prompt (34,625-char
                rendered prompt, real lecture text) direct against Z.ai's API
                at max_tokens=8192: with thinking on default, GLM used only
                705 reasoning tokens but was roughly twice as verbose
                overall, hit `finish_reason=length` and produced 2 of 8
                required summary sections with no sources/version footer —
                a production truncation bug. With thinking disabled, the
                same prompt finished with `finish_reason=stop`, all 8
                sections, the footer present, and 31,668 output chars —
                almost exactly matching the 32,087 chars Claude produced for
                the same lecture, at zero reasoning cost and within the
                existing token cap. It is not a reasoning-token problem;
                it is thinking mode making GLM too verbose to finish in
                time. Hence "disabled" by default.
        """
        self._api_key = api_key or get_effective_setting("zai_api_key") or ""
        self._model = model or get_effective_setting("zai_model") or ZAI_DEFAULT_MODEL
        self._base_url = base_url or get_effective_setting("zai_base_url") or ZAI_BASE_URL
        self._thinking = thinking or get_effective_setting("zai_thinking") or "disabled"

        logger.debug(
            "zai_adapter_init",
            model=self._model,
            base_url=self._base_url,
            thinking=self._thinking,
        )

    def _extra_request_params(self) -> dict:
        """Send Z.ai's `thinking` parameter alongside every completion call.

        See `__init__`'s `thinking` docstring for the measurement behind the
        "disabled" default.
        """
        return {"thinking": {"type": self._thinking}}
