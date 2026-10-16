"""The AgentAdapter contract, proven against every real provider adapter.

Each adapter is built by the real factory (`get_agent`) from the same per-user
settings the API would load, and only the network/CLI boundary is replaced by a
scripted `Transport`. So prompt construction, response parsing, usage metering,
output-language handling and error mapping all run for real, once per backend,
instead of being asserted separately for each provider.

Every test also runs a second time with the *shipped* prompt templates
(`services/app/prompts/*.txt`) mapped in where the adapters look for them
(`/app/prompts`, a container path), so a template variable that drifts from the
code that renders it fails here rather than in production.
"""

import json
from contextlib import ExitStack
from pathlib import Path

import pytest

from app.agents.base import (
    UNTRUSTED_INPUT_SYSTEM_PROMPT,
    AnswerResult,
    ClassificationResult,
    ConceptExtractionResult,
    CourseOpsResult,
    FlashcardData,
    QuizQuestionData,
    SummaryResult,
)
from app.agents.factory import get_agent
from app.core.exceptions import AgentError, ProviderCredentialError

from ._support import BACKEND_SETTINGS, Transport, install_transport, sample_extraction

pytestmark = pytest.mark.asyncio(loop_scope="session")

#: The AI pools' uid since SEC-006 (`studyaio` in services/app/Dockerfile).
NON_ROOT_POOL_UID = 999


@pytest.fixture(autouse=True)
def _opted_in_non_root_deployment(monkeypatch):
    """Run the adapter contract in the deployment that still spawns the CLI.

    These tests are about the adapter contract, not the uid policy: a non-root
    multi-user pool whose operator set CLAUDE_CLI_SHARED_UID_ACCEPTED. Fixing
    the euid makes the result identical as root in CI and non-root locally. The
    refusal itself is pinned in tests/safety, not here.
    """
    import os

    from app.agents import claude_code

    monkeypatch.setattr(os, "geteuid", lambda: NON_ROOT_POOL_UID)
    monkeypatch.setattr(claude_code.settings, "single_user_mode", False)
    monkeypatch.setenv("CLAUDE_CLI_SHARED_UID_ACCEPTED", "true")
    monkeypatch.delenv("CLAUDE_CLI_UID", raising=False)
    monkeypatch.delenv("CLAUDE_CLI_GID", raising=False)


BACKENDS = list(BACKEND_SETTINGS)
# The Claude Code CLI reports no token usage, so only the call is counted.
REPORTS_TOKENS = {"anthropic_api", "openai", "zai", "ollama"}
# API backends carry the trust-boundary system prompt in a dedicated channel.
HAS_SYSTEM_CHANNEL = {"anthropic_api", "openai", "zai"}

CLASSIFY = json.dumps(
    {
        "course_code": "NET101",
        "week": 3,
        "title": "Transport Layer",
        "confidence": 0.93,
        "reasoning": "header says NET101",
    }
)
SUMMARY = "# NET101 - Week 3\n\n## Overview\n\nBody.\n---JSON_META---\n" + json.dumps(
    {"embedded_images": ["img1.png"]}
)
FLASHCARDS = json.dumps(
    [
        {
            "front": "What is TCP?",
            "back": "Reliable transport",
            "tags": ["tcp"],
            "source_page_ref": 2,
        },
        {"front": "What is UDP?", "back": "Datagrams"},
    ]
)
QUIZ = json.dumps(
    [
        {
            "question_type": "multiple_choice",
            "question": "Which is reliable?",
            "options": ["A. TCP", "B. UDP", "C. IP", "D. ARP"],
            "correct_answer": "A",
            "explanation": "TCP retransmits",
            "source_page_ref": 2,
        },
        {"question": "Define MSS."},
    ]
)
ANSWER = json.dumps(
    {
        "answer": "TCP uses a handshake [1].",
        "citations": [
            {"ref": 1, "chunk_id": "c1", "text_snippet": "handshake", "course_code": "NET101"}
        ],
    }
)
COURSE_OPS = json.dumps(
    {
        "assessments": [
            {
                "title": "Midterm",
                "assessment_type": "exam",
                "weight_pct": 30,
                "weeks_relevant": [1, 2],
            },
            {"title": "Project"},
        ],
        "deadlines": [{"title": "A1", "due_date": "2030-05-01", "deadline_type": "assignment"}],
        "course_info": {"name": "Networks"},
        "confidence": 0.9,
    }
)
CONCEPTS = json.dumps(
    {
        "concepts": [
            {"name": "TCP", "description": "Reliable", "category": "protocol"},
            {"name": "Odd", "description": "x", "category": "not-a-category"},
            {"name": "  ", "description": "blank name is dropped"},
        ],
        "relations": [
            {"source": "TCP", "target": "Odd", "relation_type": "bogus", "confidence": 7},
            {"source": "", "target": "TCP"},
        ],
    }
)

CHUNKS = [
    {
        "chunk_id": "c1",
        "text": "TCP uses a three way handshake.",
        "course_code": "NET101",
        "week": 3,
        "page_ref": 2,
        "artifact_id": "a1",
    }
]


@pytest.fixture(params=[False, True], ids=["inline-prompts", "shipped-templates"])
def prompt_source(request, monkeypatch):
    """Run each test with inline fallback prompts, then with the shipped templates."""
    if request.param:
        prompts = Path(__file__).resolve().parents[2] / "prompts"
        real_exists, real_read = Path.exists, Path.read_text

        def remap(path):
            text = str(path)
            marker = "/app/prompts/"
            return prompts / text.split(marker, 1)[1] if text.startswith(marker) else path

        monkeypatch.setattr(Path, "exists", lambda self, *a, **k: real_exists(remap(self), *a, **k))
        monkeypatch.setattr(
            Path, "read_text", lambda self, *a, **k: real_read(remap(self), *a, **k)
        )
    return request.param


@pytest.fixture(params=BACKENDS)
def backend(request):
    return request.param


@pytest.fixture
def rig(backend, prompt_source):
    """(agent, transport, backend) with the provider boundary scripted."""
    transport = Transport()
    with ExitStack() as stack:
        install_transport(stack, backend, transport)
        yield get_agent(user_settings=dict(BACKEND_SETTINGS[backend])), transport, backend


class TestPromptSource:
    async def test_shipped_templates_really_are_what_the_adapters_load(self, prompt_source):
        exists = Path("/app/prompts/classify.txt").exists()
        assert exists is prompt_source
        if prompt_source:
            assert "{{" in Path("/app/prompts/classify.txt").read_text()


class TestContract:
    async def test_classify(self, rig):
        agent, transport, backend = rig
        transport.push(CLASSIFY)
        result = await agent.classify_lecture("Lecture 3 on TCP", "net-w3.pdf", ["NET101", "OS200"])
        assert result == ClassificationResult(
            course_code="NET101",
            week=3,
            title="Transport Layer",
            confidence=0.93,
            reasoning="header says NET101",
        )
        prompt = transport.prompts[0]
        assert "net-w3.pdf" in prompt and "Lecture 3 on TCP" in prompt and "OS200" in prompt
        if backend in HAS_SYSTEM_CHANNEL:
            assert transport.systems[0] == UNTRUSTED_INPUT_SYSTEM_PROMPT

    async def test_summary_new_then_update(self, rig):
        agent, transport, _ = rig
        transport.push(SUMMARY, SUMMARY)
        first = await agent.generate_summary(sample_extraction(), None)
        assert isinstance(first, SummaryResult)
        assert (
            first.content_md.startswith("# NET101 - Week 3") and "JSON_META" not in first.content_md
        )
        assert first.embedded_images == ["img1.png"]
        assert "img1.png" in transport.prompts[0]  # image references reach the model

        await agent.generate_summary(sample_extraction(), "# OLD SUMMARY TEXT")
        assert "OLD SUMMARY TEXT" in transport.prompts[1]
        assert "OLD SUMMARY TEXT" not in transport.prompts[0]

    async def test_flashcards_and_quiz(self, rig):
        agent, transport, _ = rig
        transport.push(FLASHCARDS, QUIZ)
        cards = await agent.generate_flashcards("summary text", sample_extraction(), 7)
        assert cards[0] == FlashcardData(
            front="What is TCP?", back="Reliable transport", tags=["tcp"], source_page_ref=2
        )
        assert cards[1].tags == [] and cards[1].source_page_ref == 1  # defaults applied
        assert "7" in transport.prompts[0]

        questions = await agent.generate_quiz("summary text", sample_extraction(), 5)
        assert questions[0] == QuizQuestionData(
            question_type="multiple_choice",
            question="Which is reliable?",
            options=["A. TCP", "B. UDP", "C. IP", "D. ARP"],
            correct_answer="A",
            explanation="TCP retransmits",
            source_page_ref=2,
        )
        assert questions[1].question_type == "short_answer" and questions[1].options is None

    async def test_answer_and_streaming(self, rig):
        agent, transport, backend = rig
        transport.push(ANSWER, ANSWER)
        result = await agent.answer_question("How does TCP connect?", CHUNKS)
        assert isinstance(result, AnswerResult)
        assert result.answer == "TCP uses a handshake [1]."
        assert result.citations[0]["chunk_id"] == "c1"
        assert "How does TCP connect?" in transport.prompts[0]
        assert "three way handshake" in transport.prompts[0]

        streamed = "".join([piece async for piece in agent.stream_answer("How?", CHUNKS)])
        # GL#16: the stream is plain prose equal to the answer text, never JSON scaffolding
        # (native adapters use answer_question_stream.txt; the guard unwraps a JSON reply).
        assert streamed == "TCP uses a handshake [1]."
        assert not streamed.lstrip().startswith("{")

    async def test_course_ops_and_concepts(self, rig):
        agent, transport, _ = rig
        transport.push(COURSE_OPS, CONCEPTS)
        ops = await agent.extract_course_ops("Midterm worth 30%", "NET101", "outline")
        assert isinstance(ops, CourseOpsResult)
        assert [(a.title, a.weight_pct, a.weeks_relevant) for a in ops.assessments] == [
            ("Midterm", 30, [1, 2]),
            ("Project", None, []),
        ]
        assert ops.deadlines[0].due_date == "2030-05-01" and ops.confidence == 0.9
        assert "NET101" in transport.prompts[0] and "Midterm worth 30%" in transport.prompts[0]

        concepts = await agent.extract_concepts("TCP text", ["Existing"])
        assert isinstance(concepts, ConceptExtractionResult)
        assert [(c.name, c.category) for c in concepts.concepts] == [
            ("TCP", "protocol"),
            ("Odd", "general"),  # unknown category normalised, blank name dropped
        ]
        assert [(r.source, r.relation_type, r.confidence) for r in concepts.relations] == [
            ("TCP", "related_to", 1.0)  # unknown type normalised, confidence clamped
        ]
        assert "Existing" in transport.prompts[1]

    async def test_output_language_applies_to_content_not_to_parsed_records(
        self, backend, prompt_source
    ):
        transport = Transport()
        with ExitStack() as stack:
            install_transport(stack, backend, transport)
            agent = get_agent(user_settings=dict(BACKEND_SETTINGS[backend]), output_language="ru")
            assert agent.output_language == "ru"
            transport.push(CLASSIFY, SUMMARY, FLASHCARDS, ANSWER, COURSE_OPS, CONCEPTS)
            await agent.classify_lecture("t", "f.pdf", [])
            await agent.generate_summary(sample_extraction(), None)
            await agent.generate_flashcards("s", sample_extraction(), 2)
            await agent.answer_question("q", CHUNKS)
            await agent.extract_course_ops("doc", "NET101", "outline")
            await agent.extract_concepts("text")
        directive = agent.language_directive().strip()
        assert directive
        classify, summary, cards, answer, ops, concepts = transport.prompts
        assert directive in summary and directive in cards and directive in answer
        # Parsed records stay in the schema's own vocabulary.
        assert directive not in classify and directive not in ops and directive not in concepts

    async def test_usage_is_counted_per_call(self, rig):
        agent, transport, backend = rig
        transport.push(CLASSIFY, SUMMARY)
        await agent.classify_lecture("t", "f.pdf", [])
        await agent.generate_summary(sample_extraction(), None)
        assert agent.usage.calls == 2
        if backend in REPORTS_TOKENS:
            assert (agent.usage.input_tokens, agent.usage.output_tokens) == (22, 14)
        else:
            assert agent.usage.input_tokens == 0
        agent.reset_usage()
        assert agent.usage.calls == 0

    async def test_transport_failure_becomes_agent_error(self, rig):
        agent, transport, _ = rig
        transport.fail = RuntimeError("connection reset")
        with pytest.raises(AgentError):
            await agent.classify_lecture("t", "f.pdf", [])

    async def test_unparseable_model_output_becomes_agent_error(self, rig):
        agent, transport, _ = rig
        transport.push("I'm sorry, I cannot help with that.", "not an array")
        with pytest.raises(AgentError):
            await agent.classify_lecture("t", "f.pdf", [])
        with pytest.raises(AgentError):
            await agent.generate_flashcards("s", sample_extraction(), 1)

    async def test_tolerates_fenced_and_chatty_json(self, rig):
        agent, transport, _ = rig
        transport.push(f"Sure! Here you go:\n```json\n{CLASSIFY}\n```\nHope that helps")
        result = await agent.classify_lecture("t", "f.pdf", [])
        assert result.course_code == "NET101"


class TestFactory:
    async def test_selects_the_adapter_the_user_chose(self):
        from app.agents.anthropic_api import AnthropicAPIAdapter
        from app.agents.claude_code import ClaudeCodeAdapter
        from app.agents.ollama_adapter import OllamaAdapter
        from app.agents.openai_adapter import OpenAIAdapter
        from app.agents.zai_adapter import ZaiAdapter

        expected = {
            "anthropic_api": AnthropicAPIAdapter,
            "openai": OpenAIAdapter,
            "zai": ZaiAdapter,
            "ollama": OllamaAdapter,
            "claude_code": ClaudeCodeAdapter,
        }
        for backend, cls in expected.items():
            assert type(get_agent(user_settings=dict(BACKEND_SETTINGS[backend]))) is cls

    async def test_a_chosen_provider_without_its_own_credential_is_refused(self):
        for backend, key in (
            ("anthropic_api", "anthropic_api_key"),
            ("openai", "openai_api_key"),
            ("zai", "zai_api_key"),
            ("ollama", "ollama_base_url"),
            ("claude_code", "claude_cli_credentials"),
        ):
            with pytest.raises(ProviderCredentialError):
                get_agent(user_settings={"agent_backend": backend, key: "  "})

    async def test_unparseable_cli_credentials_are_refused_not_defaulted(self):
        with pytest.raises(ProviderCredentialError):
            get_agent(
                user_settings={
                    "agent_backend": "claude_code",
                    "claude_cli_credentials": "{not json",
                }
            )

    async def test_no_settings_uses_the_instance_backend(self):
        from unittest.mock import patch

        with patch("app.config.settings.agent_backend", "ollama"):
            from app.agents.ollama_adapter import OllamaAdapter

            assert isinstance(get_agent(), OllamaAdapter)
        assert type(get_agent(user_settings={"agent_backend": "studyaio"})).__name__ in {
            "ClaudeCodeAdapter",
            "OllamaAdapter",
            "OpenAIAdapter",
            "AnthropicAPIAdapter",
            "ZaiAdapter",
        }

    async def test_unsupported_language_falls_back_to_english(self):
        agent = get_agent(user_settings=dict(BACKEND_SETTINGS["ollama"]), output_language="xx")
        assert agent.output_language is None and agent.language_directive() == ""


class TestApiAdapters:
    async def test_missing_api_key_is_a_configuration_error(self):
        from app.agents.anthropic_api import AnthropicAPIAdapter
        from app.agents.openai_adapter import OpenAIAdapter

        for adapter in (AnthropicAPIAdapter(api_key="", model="haiku"), OpenAIAdapter(api_key="")):
            adapter._api_key = ""
            with pytest.raises(AgentError, match="not configured"):
                await adapter._call_api("hi")

    async def test_model_selection(self):
        from app.agents.anthropic_api import MODEL_MAP, AnthropicAPIAdapter

        assert AnthropicAPIAdapter(api_key="k", model="haiku")._model == MODEL_MAP["haiku"]
        assert AnthropicAPIAdapter(api_key="k", model="nonsense")._model == MODEL_MAP["sonnet"]

    async def test_zai_sends_thinking_parameter_and_custom_endpoint(self):
        from unittest.mock import patch

        from app.agents.zai_adapter import ZAI_BASE_URL, ZaiAdapter

        sent = {}

        class Client:
            def __init__(self, api_key=None, base_url=None, **_):
                sent["base_url"] = base_url
                self.chat = type(
                    "C", (), {"completions": type("X", (), {"create": staticmethod(self._create)})}
                )

            async def _create(self, **kw):
                sent.update(kw)
                from types import SimpleNamespace

                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))], usage=None
                )

        with patch("app.agents.openai_adapter.AsyncOpenAI", Client):
            adapter = ZaiAdapter(api_key="k")
            assert await adapter._call_api("hi") == "ok"
        assert sent["base_url"] == ZAI_BASE_URL
        assert sent["extra_body"] == {"thinking": {"type": "disabled"}}
        assert adapter.usage.calls == 1 and adapter.usage.input_tokens == 0


class TestClaudeCodeAdapter:
    def _agent(self, **kw):
        return get_agent(user_settings={**BACKEND_SETTINGS["claude_code"], **kw})

    async def test_prompt_goes_on_stdin_never_argv(self):
        from unittest.mock import patch

        seen = {}

        async def fake_exec(*cmd, **kw):
            seen["cmd"] = cmd

            class Proc:
                returncode = 0

                async def communicate(self, input=None):
                    seen["stdin"] = input
                    return b"ok", b""

            return Proc()

        agent = self._agent()
        with patch("asyncio.create_subprocess_exec", fake_exec):
            assert await agent._run_claude_code("SECRET-LECTURE-TEXT") == "ok"
        assert "SECRET-LECTURE-TEXT" not in " ".join(seen["cmd"])
        assert seen["stdin"] == b"SECRET-LECTURE-TEXT"

    async def test_user_credentials_are_private_and_removed_afterwards(self):
        import os
        import stat
        from unittest.mock import patch

        seen = {}

        async def fake_exec(*cmd, env=None, **kw):
            config_dir = env["CLAUDE_CONFIG_DIR"]
            creds_file = os.path.join(config_dir, ".credentials.json")
            seen["dir"] = config_dir
            seen["mode"] = stat.S_IMODE(os.stat(creds_file).st_mode)
            seen["content"] = json.load(open(creds_file))
            # The CLI refreshes the token in place.
            refreshed = {
                "claudeAiOauth": {"accessToken": "NEW", "refreshToken": "r", "expiresAt": 2}
            }
            json.dump(refreshed, open(creds_file, "w"))

            class Proc:
                returncode = 0

                async def communicate(self, input=None):
                    return b"fine", b""

            return Proc()

        agent = self._agent()
        with patch("asyncio.create_subprocess_exec", fake_exec):
            await agent._run_claude_code("hi")
        assert seen["mode"] == 0o600
        assert seen["content"]["claudeAiOauth"]["accessToken"] == "a"
        assert not os.path.exists(seen["dir"])  # credentials never left on disk
        assert agent.refreshed_credentials["claudeAiOauth"]["accessToken"] == "NEW"

    async def test_cli_failure_reports_both_streams(self):
        from unittest.mock import patch

        async def fake_exec(*cmd, **kw):
            class Proc:
                returncode = 1

                async def communicate(self, input=None):
                    return b"401 OAuth access token has been revoked", b"Sandbox disabled: no bwrap"

            return Proc()

        with patch("asyncio.create_subprocess_exec", fake_exec):
            with pytest.raises(AgentError) as err:
                await self._agent()._run_claude_code("hi")
        message = str(err.value)
        assert "exit 1" in message and "revoked" in message and "bwrap" in message

    async def test_missing_cli_and_timeout(self):
        import asyncio
        from unittest.mock import patch

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with pytest.raises(AgentError, match="not found"):
                await self._agent(claude_code_path="/no/such/claude")._run_claude_code("hi")

        killed = []

        async def slow_exec(*cmd, **kw):
            class Proc:
                returncode = None

                async def communicate(self, input=None):
                    await asyncio.sleep(5)

                def kill(self):
                    killed.append(True)

            return Proc()

        with patch("asyncio.create_subprocess_exec", slow_exec):
            with pytest.raises(AgentError, match="timed out"):
                await self._agent()._run_claude_code("hi", timeout=0)
        assert killed
