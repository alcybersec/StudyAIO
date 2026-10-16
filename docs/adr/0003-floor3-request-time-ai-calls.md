# ADR 0003 — Floor 3 admits an enumerated set of request-time AI calls

**Status** Accepted · **Date** 2026-10-04 · **Kit version** 1.10.3

**Amended by** [ADR 0005](0005-floor3-embedding-gateway.md) (Accepted 2026-10-04; header corrected 2026-10-08, it previously said "proposed"): embeddings are in scope of floor 3 through a second gateway, `get_embedding_provider`, with its own allowlist. This ADR's `get_agent` decision is unchanged. The open embeddings question under Consequences is answered there.

Accepted: the user agreed in session on 2026-10-04 to amend floor 3 rather than move these calls
into the worker. This ADR weakens a floor, so it is the record `docs/strategy.md` §6 requires —
an ADR plus the user's explicit agreement.

## Context

Floor 3 (`docs/strategy.md` §6) reads:

> AI only via the adapter: no AI call bypasses AgentAdapter, and none is made from an API route,
> only from the Celery worker

Recording `agents.AgentAdapter` v1 as built (M31-S1-ARCH-001, `docs/CONTRACTS.md`, ADR 0002)
showed that the first clause holds and the second does not. Every generative call obtains its
adapter from `app.agents.factory.get_agent`, and no module outside `app/agents/**` imports a
provider SDK (`anthropic`, `openai`, `ollama`) or spawns the `claude` CLI. But five functions
call `get_agent` in the API process, inside the request that triggered them.

Re-derived on 2026-10-04 at `7cd283c` with `grep -rn "get_agent" services/app/app/`, excluding
`app/agents/**` (the definition) and `app/pipeline/**` (the worker):

| # | Call site (`services/app/`) | Enclosing function | Route (handler) | Adapter method |
|---|---|---|---|---|
| 1 | `app/api/qa.py:110` | `ask_question` | `POST /api/qa/ask` (`api/qa.py:33`) | `answer_question` |
| 2 | `app/api/settings.py:111` | `test_ai_connection` | `POST /api/settings/test-ai` (`api/settings.py:78`) | `classify_lecture` |
| 3 | `app/services/chat_service.py:480` | `send_message` | `POST /api/chat/sessions/{session_id}/messages` (`api/chat.py:161`) | `answer_question` |
| 4 | `app/services/chat_service.py:646` | `stream_message` | `POST /api/chat/sessions/{session_id}/messages/stream` (`api/chat.py:224`) | `stream_answer` |
| 5 | `app/services/concept_service.py:112` | `extract_and_save_concepts` | `POST /api/concepts/extract/{artifact_id}` (`api/concepts.py:160`) | `extract_concepts` |

No sixth site exists. The worker-side sites are `app/pipeline/classify.py:215`,
`summarize.py:178`, `assets.py:112`, `courseops_task.py:92` and `targeted_task.py:420` (the last
added in M33 by ADR 0007, worker-side, so no amendment here).

**Line numbers refreshed 2026-10-16 at `b81e5d6`** (M34-S2-SEC-009, M33 floors note N-4), by the
same grep. The `(module, enclosing function)` set is unchanged and the floor test agrees with it;
only the `file:line` cells moved. A route cell is the line of its `@router.post(` decorator. Line
numbers are a reading aid: the allowlist below is keyed on the function, and the floor test reads
the code, not this table.

Each of the five answers the user in the same request: live Q&A and chat return the answer (chat
streams it token by token over SSE), the settings probe reports whether the user's credentials
work, and concept extraction returns the extracted graph in its `201` body. Moving them to the
worker would mean a job-and-poll protocol for each, and would break token streaming outright.

## Decision

**1. Floor 3 is reworded** to:

> AI only via the adapter: every AI call goes through AgentAdapter, obtained via `get_agent`;
> `get_agent` is called only in `app/pipeline/**` (the Celery worker) and at the request-time
> call sites enumerated in ADR 0003, and a new request-time call site requires amending that ADR.

The Orchestrator carries this text into `docs/strategy.md` §6, `.claude/kit.yaml` and `CLAUDE.md`;
this ADR does not edit them.

**2. The allowlist is exact.** It is the set of `(module, enclosing function)` pairs below, keyed
on the function, not the line, so that edits elsewhere in a file do not churn it:

```python
REQUEST_TIME_GET_AGENT_CALL_SITES = {
    ("app/api/qa.py", "ask_question"),
    ("app/api/settings.py", "test_ai_connection"),
    ("app/services/chat_service.py", "send_message"),
    ("app/services/chat_service.py", "stream_message"),
    ("app/services/concept_service.py", "extract_and_save_concepts"),
}
```

A function on this list may contain more than one `get_agent` call without amending the ADR; a
new function, or an existing one moved to another module, may not.

**3. What stays absolute.** The first clause is unchanged in force: no module outside
`app/agents/**` constructs an adapter class directly, imports a provider SDK, or invokes the
`claude` CLI. Every request-time site still goes through `get_agent`, so per-user credentials,
`ProviderCredentialError` and output language behave identically in both processes.

## Consequences

- **This is a weakening of a floor**, recorded per `docs/strategy.md` §6. Before it, any AI call in
  the API process was a floor breach; after it, five named ones are not. The set can grow only by
  amending this ADR, which needs the same user agreement.
- **What the floor test checks** (M31-S1-SAFETY-003, owned by `safety`):
  1. Walking the AST of every module under `services/app/app/` except `app/agents/**` and
     `app/pipeline/**`, the set of `(module, enclosing function)` pairs that call `get_agent` equals
     `REQUEST_TIME_GET_AGENT_CALL_SITES` exactly — a missing entry and an extra entry both fail.
  2. No module outside `app/agents/**` imports `anthropic`, `openai` or `ollama` (at module level
     or inside a function), references an adapter class (`ClaudeCodeAdapter`,
     `AnthropicAPIAdapter`, `OpenAIAdapter`, `ZaiAdapter`, `OllamaAdapter`) other than in a
     docstring or comment, or starts a subprocess whose program is the `claude` CLI — the literal
     `"claude"` or a `claude_code_path` setting. (`settings_service` may still read and validate
     `claude_code_path`; only spawning it is reserved to `app/agents/**`.)
  3. Every `get_agent` call under `app/pipeline/**` sits in a module that registers a Celery task.
- **Request-time sites run on the API's event loop and timeouts.** A slow provider holds an API
  worker for the duration of the call. Rate limits (`concepts` is `10/minute`) and the AI quota
  check (`quota_service.check_ai_quota`) are the only back-pressure; that is accepted, not solved.
- **`CLAUDE.md` is wrong about concept extraction.** It lists
  `app.pipeline.concepts_task.extract_concepts` as the on-demand handler for
  `POST /api/concepts/extract/{artifact_id}`. As built, the route calls
  `concept_service.extract_and_save_concepts` in-request (`api/concepts.py:210` at `b81e5d6`);
  the Celery task is registered but nothing in `services/app/app/` enqueues it. This ADR records the discrepancy
  and does not edit `CLAUDE.md`; correcting the line, and deciding whether the unused task stays,
  is the Orchestrator's call.
- **`docs/CONTRACTS.md`** — the `agents.AgentAdapter` v1 entry's open question against floor 3 is
  closed by reference to this ADR. The interface is unchanged, so it stays v1.
- **Open, not decided here: embeddings.** `app/agents/embeddings.py` defines `EmbeddingProvider`,
  a separate abstraction from `AgentAdapter`, with `OpenAIEmbeddingProvider` and
  `OllamaEmbeddingProvider` that call a remote model. It is called at request time
  (as of `b81e5d6`: `api/qa.py:66`, `services/chat_service.py:454` and `:612`,
  `services/concept_service.py:47`)
  and in the worker (`pipeline/index.py`). Floor 3 never said whether an embedding is an "AI call".
  If it is, these calls bypass `AgentAdapter` under the old wording and the new one alike. The
  floor test above does not catch them, because the SDK imports sit inside `app/agents/**`. This
  needs a ruling from the user and `safety`; this ADR neither widens nor narrows the term.
