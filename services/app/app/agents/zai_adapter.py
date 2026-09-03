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

    def __init__(self, api_key: str = "", model: str = "", base_url: str = ""):
        """Configure the adapter.

        Args:
            api_key: Z.ai API key. Falls back to the `zai_api_key` setting.
            model: GLM model id. Falls back to `zai_model`, then the default.
            base_url: Override the endpoint. Falls back to `zai_base_url`,
                then Z.ai's public endpoint — self-hosted GLM deployments and
                regional endpoints exist, so this stays configurable.
        """
        self._api_key = api_key or get_effective_setting("zai_api_key") or ""
        self._model = model or get_effective_setting("zai_model") or ZAI_DEFAULT_MODEL
        self._base_url = base_url or get_effective_setting("zai_base_url") or ZAI_BASE_URL

        logger.debug("zai_adapter_init", model=self._model, base_url=self._base_url)
