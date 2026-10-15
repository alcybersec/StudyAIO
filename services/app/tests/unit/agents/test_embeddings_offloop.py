"""Embedding must not block the event loop (GL#50, audit TECH-07).

`SentenceTransformerProvider.embed_texts` is CPU-bound and synchronous, and ADR 0005
pins `EmbeddingProvider`'s public surface, so the off-loop entry point is the module
function `aembed_texts`, and the local provider is made safe to call from a worker
thread (single model load, serialised encode).
"""

import asyncio
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from app.agents import embeddings
from app.agents.embeddings import SentenceTransformerProvider, aembed_texts


class SlowProvider(embeddings.EmbeddingProvider):
    """Blocks the calling thread like a real encode would."""

    def __init__(self, delay: float = 0.3):
        self.delay = delay
        self.thread: str | None = None

    @property
    def dimensions(self) -> int:
        return 2

    def preload(self) -> None:
        return None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.thread = threading.current_thread().name
        time.sleep(self.delay)
        return [[1.0, 2.0] for _ in texts]


class TestAembedTexts:
    @pytest.mark.asyncio
    async def test_encode_runs_off_the_event_loop_thread(self):
        provider = SlowProvider(0.01)
        main = threading.current_thread().name

        out = await aembed_texts(provider, ["a", "b"])

        assert out == [[1.0, 2.0], [1.0, 2.0]]
        assert provider.thread is not None and provider.thread != main

    @pytest.mark.asyncio
    async def test_loop_stays_responsive_during_a_slow_encode(self):
        provider = SlowProvider(0.4)
        ticks: list[float] = []

        async def heartbeat() -> None:
            while True:
                ticks.append(time.monotonic())
                await asyncio.sleep(0.02)

        beat = asyncio.create_task(heartbeat())
        try:
            await aembed_texts(provider, ["x"])
        finally:
            beat.cancel()

        # A blocked loop would record one or two ticks across a 0.4s encode.
        assert len(ticks) >= 8
        assert max(b - a for a, b in zip(ticks, ticks[1:], strict=False)) < 0.2

    @pytest.mark.asyncio
    async def test_empty_input_does_not_touch_the_provider(self):
        provider = SlowProvider(0)
        assert await aembed_texts(provider, []) == []
        assert provider.thread is None

    @pytest.mark.asyncio
    async def test_provider_errors_propagate(self):
        provider = SlowProvider(0)
        provider.embed_texts = MagicMock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="boom"):
            await aembed_texts(provider, ["x"])


def _fake_model_class(loads: list[int], on_encode=None, load_delay: float = 0.0):
    class FakeModel:
        max_seq_length = 256

        def __init__(self, name: str):
            loads.append(1)
            time.sleep(load_delay)

        def get_sentence_embedding_dimension(self) -> int:
            return 384

        def encode(self, texts, show_progress_bar=False):
            if on_encode:
                on_encode()
            return [MagicMock(tolist=lambda: [0.0] * 384) for _ in texts]

    return FakeModel


def _run_threads(target, n: int) -> None:
    threads = [threading.Thread(target=target) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


class TestLocalProviderThreadSafety:
    def test_concurrent_first_use_loads_the_model_once(self):
        loads: list[int] = []
        provider = SentenceTransformerProvider()
        module = MagicMock(SentenceTransformer=_fake_model_class(loads, load_delay=0.1))
        with patch.dict("sys.modules", {"sentence_transformers": module}):
            _run_threads(lambda: provider.embed_texts(["a"]), 6)

        assert len(loads) == 1

    def test_encodes_are_serialised(self):
        state = {"active": 0, "peak": 0}
        guard = threading.Lock()

        def on_encode() -> None:
            with guard:
                state["active"] += 1
                state["peak"] = max(state["peak"], state["active"])
            time.sleep(0.05)
            with guard:
                state["active"] -= 1

        provider = SentenceTransformerProvider()
        module = MagicMock(SentenceTransformer=_fake_model_class([], on_encode))
        with patch.dict("sys.modules", {"sentence_transformers": module}):
            _run_threads(lambda: provider.embed_texts(["a"]), 4)

        assert state["peak"] == 1
