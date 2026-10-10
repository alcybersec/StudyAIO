# ADR 0005 — Floor 3 covers embeddings through a second gateway, `get_embedding_provider`

**Status** Accepted (2026-10-04, by the user) · **Date** 2026-10-04 · **Kit version** 1.10.3 · **Amends** ADR 0003

**Ruling implemented:** `docs/decisions.md` § Rulings, 2026-10-04, "R-004 embeddings: **in scope of
floor 3** — `EmbeddingProvider` is a second sanctioned gateway with its own enumerated allowlist"
(by: user). That ruling settles the substance. This ADR adds the wording and the allowlist. The user
accepted that text as written on 2026-10-04.

## Context

ADR 0003 left one question open:

> `app/agents/embeddings.py` defines `EmbeddingProvider`, a separate abstraction from
> `AgentAdapter` … Floor 3 never said whether an embedding is an "AI call".

The user ruled that it is. The floor as worded by ADR 0003 cannot hold that ruling, because every
embedding call bypasses `AgentAdapter`. That is by design, not by accident:

- **One instance-wide model.** Every vector in `chunks.embedding` and `concepts.embedding` must come
  from the same model, so the comparison is meaningful. `get_embedding_provider` deliberately reads
  only `EMBEDDING_BACKEND` and never takes per-user credentials (its docstring explains why, under
  issue #32). Routing embeddings through `get_agent`, which resolves per-user credentials, would
  break that invariant.
- **A different interface.** `AgentAdapter` is generative: prompt in, structured answer out.
  `EmbeddingProvider` is `embed_texts(list[str]) -> list[list[float]]`. Adding `embed_texts` to
  `AgentAdapter` would force four generative backends to implement a method they cannot honour
  consistently, and would bump `agents.AgentAdapter` to v2 for no consumer benefit.

So the ruling is implemented as a **second sanctioned gateway**. It is held to the same standard as
the first: one factory, an exact allowlist of call sites, and no way around it.

Re-derived on 2026-10-04 at `f1fc455`, using
`grep -rn "get_embedding_provider\|embed_texts\|EmbeddingProvider" services/app/app/` and excluding
`app/agents/**`, which is where the gateway is defined:

| # | Call site (`services/app/`) | Enclosing function | Reached from | Calls |
|---|---|---|---|---|
| 1 | `app/api/qa.py:57` | `ask_question` | `POST /api/qa/ask`, in the request | `get_embedding_provider`, `embed_texts` |
| 2 | `app/services/chat_service.py:196` | `send_message` | `POST /api/chat/sessions/{id}/messages`, in the request | `get_embedding_provider`, `embed_texts` |
| 3 | `app/services/chat_service.py:330` | `stream_message` | `POST /api/chat/sessions/{id}/messages/stream`, in the request | `get_embedding_provider`, `embed_texts` |
| 4 | `app/services/concept_service.py:40` | `_embed_concepts` | `concept_service.extract_and_save_concepts`. That function runs in the request for `POST /api/concepts/extract/{id}`, and in the worker for `pipeline/concepts_task.py` and `pipeline/assets.py` | `get_embedding_provider`, `embed_texts` |
| 5 | `app/main.py:229` | `warn_if_embedding_provider_unavailable` | API lifespan startup, **not** a request | `get_embedding_provider`, `preload` (no `embed_texts`) |
| 6 | `app/services/index_service.py:171` | `index_artifact_chunks` | `pipeline/index.py:_index` only, and that function hands in the provider | `embed_texts` on the injected provider; it never calls `get_embedding_provider` |
| W | `app/pipeline/index.py:76` | `_index` | Celery task `index_artifact` | `get_embedding_provider` |

No other site exists. Sites 1 to 4 are the same four that ADR 0003 and `FLOORS.md` §3 named.
Sites 5 and 6 are new: the grep turned them up, and the open question in ADR 0003 did not mention
them.

## Decision

**1. Floor 3 is reworded** to:

> AI only via the adapter: every AI call goes through a sanctioned gateway, either AgentAdapter
> obtained via `get_agent`, or, for embeddings, EmbeddingProvider obtained via
> `get_embedding_provider`; outside `app/agents/**` and `app/pipeline/**` (the Celery worker),
> each gateway is called only at the call sites enumerated in ADR 0003 (`get_agent`) and ADR 0005
> (`get_embedding_provider`), and a new such call site requires amending the ADR that lists it.

ADR 0003's `get_agent` allowlist and its three checks are unchanged. This ADR adds the second
gateway alongside them.

**2. "AI call" includes every embedding, whatever the backend.** That covers a remote one
(`openai`, `ollama`) and a local one (`sentence_transformers`) alike. The floor is defined by the
gateway, not by whether the call leaves the network. A model that runs in-process today can become
a remote one tomorrow when someone changes `EMBEDDING_BACKEND`, and the call site cannot tell the
difference.

**3. The allowlists are exact.** Like ADR 0003's, they are keyed on `(module, enclosing function)`,
and they cover `services/app/app/` excluding `app/agents/**` and `app/pipeline/**`:

```python
#: Callers of `get_embedding_provider` outside app/agents/** and app/pipeline/**.
GET_EMBEDDING_PROVIDER_CALL_SITES = {
    ("app/api/qa.py", "ask_question"),
    ("app/services/chat_service.py", "send_message"),
    ("app/services/chat_service.py", "stream_message"),
    ("app/services/concept_service.py", "_embed_concepts"),
    ("app/main.py", "warn_if_embedding_provider_unavailable"),
}

#: Callers of `.embed_texts(...)` outside app/agents/** and app/pipeline/**.
EMBED_TEXTS_CALL_SITES = {
    ("app/api/qa.py", "ask_question"),
    ("app/services/chat_service.py", "send_message"),
    ("app/services/chat_service.py", "stream_message"),
    ("app/services/concept_service.py", "_embed_concepts"),
    ("app/services/index_service.py", "index_artifact_chunks"),
}

#: Startup-only sites: may call `get_embedding_provider` and `.preload()`, never `.embed_texts`.
STARTUP_ONLY_EMBEDDING_SITES = {
    ("app/main.py", "warn_if_embedding_provider_unavailable"),
}

#: A site that embeds with an injected provider must have exactly these callers, all worker-side.
INJECTED_PROVIDER_CALLERS = {
    ("app/services/index_service.py", "index_artifact_chunks"): {
        ("app/pipeline/index.py", "_index"),
    },
}

#: The gateway's interface and its backends. The contract test pins both against
#: app/agents/embeddings.py, so a new method or backend cannot slip past the call-site pins.
EMBEDDING_PROVIDER_SURFACE = {"dimensions", "embed_texts", "preload"}
EMBEDDING_BACKENDS = {
    "sentence_transformers": "SentenceTransformerProvider",
    "openai": "OpenAIEmbeddingProvider",
    "ollama": "OllamaEmbeddingProvider",
}
```

A function on these lists may contain more than one call without amending this ADR. A new
function, or a listed one moved to another module, may not.

**4. What stays absolute.** Outside `app/agents/**`:

- no module constructs an `EmbeddingProvider` subclass directly;
- no module imports `sentence_transformers`;
- no module references `SentenceTransformerProvider`, `OpenAIEmbeddingProvider` or
  `OllamaEmbeddingProvider` other than in a docstring or comment;
- no module calls `reset_embedding_provider`. That is a test seam, not a way to choose a backend.

ADR 0003 already bans importing `openai` and `ollama` outside `app/agents/**`. This ADR adds
`sentence_transformers` to that list.

## Consequences

- **This widens the floor's scope and admits the existing sites.** Before this ADR, embedding calls
  were outside the floor and unchecked. After it, they are inside the floor, and only the listed
  ones are allowed. No live call becomes a violation, because every existing site is on the list.
  Like ADR 0003, it needs the user's agreement, and the user ruled on 2026-10-04.
- **Why a new ADR rather than editing ADR 0003.** ADR 0003 is Accepted, and an accepted ADR is a
  record of what was agreed, when, and on what evidence. Rewriting its Decision would erase the
  state that `docs/gates/M31/floors.md` certified against. This ADR **amends** 0003 and does not
  supersede it, because every word of 0003's `get_agent` decision still stands. 0003 gets a
  one-line forward pointer in its header, and its open embeddings question is closed by reference
  to this ADR. Its Decision text is not touched.
- **What `safety` adds** to `services/app/tests/safety/test_floor3_ai_via_adapter.py` and to
  `FLOORS.md` §3. This is a request, not an edit:
  1. The set of `(module, function)` pairs calling `get_embedding_provider` outside agents and
     pipeline must equal `GET_EMBEDDING_PROVIDER_CALL_SITES` exactly.
  2. The same check applies to `.embed_texts(` against `EMBED_TEXTS_CALL_SITES`.
  3. No site in `STARTUP_ONLY_EMBEDDING_SITES` may call `.embed_texts`.
  4. The callers of each `INJECTED_PROVIDER_CALLERS` key must equal its listed set.
  5. Every `get_embedding_provider` call under `app/pipeline/**` must sit in a module that
     registers a Celery task. This is ADR 0003's check 3, applied to this gateway.
  6. The section 4 bans above apply, and `sentence_transformers` is added to the SDK-import check.
  7. The non-vacuity check must find `pipeline/index.py:_index` and the `openai`,
     `sentence_transformers` and `ollama` imports in `agents/embeddings.py`.
- **What the contract test pins** (`services/app/tests/contracts/test_embedding_gateway_contract.py`,
  owned by `architect`): `EMBEDDING_PROVIDER_SURFACE` and `EMBEDDING_BACKENDS` against
  `app/agents/embeddings.py`, plus the factory signature. A new public method, such as
  `embed_query`, would let a call go around the `embed_texts` pin. With this test, adding one fails
  until this ADR and safety's detector are both updated.
- **Floor 2 is untouched.** The embedding backend uses instance credentials only
  (`settings.openai_api_key`) and never reads a user's. The existing redaction of instance
  credentials covers it.
- **`ai` should correct a docstring.** The module docstring of `app/agents/embeddings.py` says
  embeddings "don't require generative AI", which is true. Read alongside the floor, though, it
  invites the conclusion that they are not AI calls, and the user ruled the opposite. A one-line
  pointer to this ADR would prevent that misreading. This is a request to `ai`, not an edit.
- **Request-time load.** Sites 1 to 4 run on the API event loop, as ADR 0003's do. `embed_texts`
  is synchronous, so for `sentence_transformers` it blocks the event loop for the duration of the
  encode. That is accepted, as in ADR 0003, and not solved here.

## Alternatives considered

- **Route embeddings through `AgentAdapter` (one gateway).** This lost because it breaks the
  single-model invariant (`get_agent` resolves per-user credentials and backends), and because it
  forces an `embed_texts` method onto four generative backends, which means a breaking bump to
  `agents.AgentAdapter` v2.
- **Move every embedding call into the worker.** This lost because Q&A and chat need the query
  embedded inside the request, before retrieval, and streaming chat could not wait on a
  job-and-poll round trip. It is the same reason ADR 0003 admitted its five request-time sites.
- **Rule that embeddings are not AI calls, and pin only that they stay under `app/agents/**`.** This
  is the other half of `FLOORS.md` §3's either-way plan. It lost because the user ruled the other
  way.
- **Edit ADR 0003 in place.** This lost for the reason given under Consequences: it would rewrite an
  accepted record that a gate certified against.
