# App-wide language select

**Status:** built, 2026-09-29. See `docs/PROGRESS.md` § "App-Wide Language
Select" for what shipped.
**Branch:** `feat/language-select` — one MR to `main` when the whole feature is done.
**Languages:** English and Russian.

## What the user asked for

One language setting, plus a toggle choosing how far it reaches:

- **Interface only** — menus, buttons, labels, errors in Russian; AI output unchanged.
- **Interface and study material** — the above, plus summaries, flashcards, quiz
  questions and chat answers generated in Russian.

Two settings, not one enum: `language` says *which*, `content_language` says
*how far*. Keeping them separate means turning content translation off does not
lose the interface preference, and a future third language needs no new states.

---

## 1. What is translated, and what deliberately is not

| Prompt | Translated? | Why |
|---|---|---|
| `summarize.txt` | yes (body) | The thing students read for hours |
| `summarize_update.txt` | yes (body) | Same document, incremental path |
| `generate_flashcards.txt` | yes | Read and recalled directly |
| `generate_quiz.txt` | yes | Read and answered directly |
| `answer_question.txt` | yes | A reply to the user |
| `study_companion_system.txt` | yes | Conversational |
| `classify.txt` | **no** | Emits course codes and week numbers the app parses |
| `extract_course_ops.txt` | **no** | Emits dates, assessment names, structured records |
| `extract_concepts.txt` | **no** | Emits a fixed category enum and graph node names |

The line is whether a human reads the output or the app parses it. Translating
the parsed three breaks ingestion and gains a student nothing.

### Section headings stay English

`## Overview`, `## Key Concepts` and the rest are load-bearing:

- `tests/golden/test_summary_structure.py::TestPromptContract` derives the
  expected list from `summarize.txt` and fails if it moves.
- `summary_service` splits summaries on those headings when merging a week.
- `docs/PRD.md` §Summary Format pins the order.

So the instruction is explicit: **translate the prose, keep the headings**. A
Russian summary under English section headers is slightly odd to read and
entirely safe; the alternative is a parser that has to know every locale.

---

## 2. Backend

### 2.1 Schema

`user_settings` already carries `theme` as a first-class column beside a
`settings_json` blob. Mirror it exactly:

| Column | Type | Default |
|---|---|---|
| `language` | `String(5)` | `'en'` |
| `content_language` | `Boolean` | `false` |

`String(5)` holds BCP-47 short tags (`en`, `ru`, later `pt-BR`). Defaulting
`content_language` to false means **no existing user's output changes** when this
ships — a silent switch to Russian summaries for someone who only wanted a
Russian menu would be a bad surprise.

Migration: additive, both non-null with server defaults, no backfill needed.

### 2.2 The constraint that shapes the design

`get_user_agent_config()` **returns `None` for every user on instance
credentials** — that is deliberate, and it is what issue #30 hardened. Language
therefore cannot ride inside that dict: most users would never get their
preference, and the ones who did would be exactly the users running their own
API keys.

So `get_agent()` takes language as its **own parameter**:

```python
def get_agent(
    user_settings: dict[str, Any] | None = None,
    output_language: str | None = None,
) -> AgentAdapter
```

Credentials and content preferences are different concerns arriving by different
routes, and the signature should say so.

### 2.3 Threading it through

Nine `get_agent()` call sites. Six pass a language, three do not:

| Call site | Language? |
|---|---|
| `pipeline/summarize.py` | yes |
| `pipeline/assets.py` | yes (flashcards + quiz) |
| `services/chat_service.py` (×2) | yes |
| `api/qa.py` | yes |
| `services/concept_service.py` | **no** — concept graph is parsed |
| `pipeline/classify.py` | **no** — metadata |
| `pipeline/courseops_task.py` | **no** — structured records |
| `api/settings.py` (test-ai) | **no** — a connectivity probe |

Each site that needs it fetches the user's preference alongside the agent config
it already fetches. A new `settings_service.get_user_output_language(session,
user_id) -> str | None` returns the tag only when `content_language` is on, so
call sites never have to know the toggle exists.

### 2.4 Adapters

Four adapters, each loading and rendering its own prompts — 14-16 render sites
apiece. Rather than thread a template variable through ~60 call sites, add one
method to `AgentAdapter`:

```python
def language_directive(self) -> str:
    """Instruction appended to content prompts, empty when output is English."""
```

and append it in the four **content** methods of each adapter (summary,
flashcards, quiz, answer) — 16 one-line insertions, each visible at the point
where the prompt is assembled.

The directive names the language, tells the model to translate prose only, and
says the headings stay as written.

### 2.5 API

`SettingsResponse` gains `language: str = "en"` and `content_language: bool =
False`; `SettingsUpdateRequest` gains the nullable pair. `PUT /api/settings`
already does partial updates, so no new endpoint.

Validation: `language` must be one of a `SUPPORTED_LANGUAGES` constant. An
unknown tag is rejected rather than silently stored, because a typo would
otherwise reach the prompt as `Write in xx`.

---

## 3. Frontend

### 3.1 Infrastructure

No i18n library today; **229 `.tsx` files** with strings inline.

Use `react-i18next` — the default for this stack, supports lazy-loaded
namespaces, and its `useTranslation()` hook fits the existing component style.
Translation files as `src/locales/{en,ru}/common.json`.

English is authored as the key set rather than as bare keys (`t('Save')` rather
than `t('settings.save')`) so that an untranslated string renders as correct
English instead of a raw key. A missing Russian entry degrades to English, which
is the right failure for a beta.

### 3.2 The selector

Goes in `AppearanceSection`, beside the theme control it mirrors:

- a two-option language control (English / Русский)
- a switch, enabled only when language is not English: **"Also generate study
  material in this language"**, bound to `content_language`

Disabled-at-English is deliberate: "generate content in English" is the existing
behaviour and offering it as a toggle implies a choice that does nothing.

### 3.3 Coverage, stated honestly

Translating 229 files is a larger mechanical job than one pass. This feature
delivers the infrastructure plus the surfaces a user meets constantly:

- navigation and layout (`Sidebar`, `Header`, `MobileNav`)
- `SettingsPage` and its sections
- auth pages (login, register, forgot/reset password)
- `Dashboard` and empty/error/loading states
- shared `components/ui` primitives

Deferred, and to be named in the MR rather than implied complete: admin panel,
knowledge graph, study hub internals, billing, gamification copy.

### 3.4 Persistence

The setting lives server-side in `user_settings` and reaches the client via the
settings query that already runs. `localStorage` mirrors it only so the first
paint before the query resolves is not in the wrong language — the server stays
authoritative, exactly as `useTheme` does.

---

## 4. Tests

**Backend**
- Settings round-trip; an unsupported tag is rejected.
- `get_user_output_language` returns `None` when `content_language` is off, even
  with `language='ru'` — the toggle is what gates it.
- `language_directive()` is empty for English and non-empty for Russian.
- Each content method includes the directive; each **metadata** method does not.
  (The load-bearing pair — a directive leaking into `classify` would break
  ingestion silently.)
- `get_agent(output_language=...)` survives `user_settings=None`, the instance-
  credential path most users are on.

**Frontend**
- The selector renders and persists through the settings mutation.
- The content toggle is disabled at English.
- A missing Russian key falls back to English rather than rendering the key.

**Golden**
- `TestPromptContract` must still pass unchanged: proof that headings did not
  move.

---

## 5. Risks

**Summary quality in Russian is unmeasured.** The eval cases are English and
their `must_mention` terms are English; a Russian summary would score 0%
coverage against them. The harness cannot validate this, and saying so is better
than shipping a number that looks like validation. First Russian summaries need
reading by a human who speaks it.

**Mixed-language output is likely at first.** Lecture material is English;
technical terms usually stay English inside Russian prose. That is normal and
probably desirable, but it will look inconsistent and is worth seeing before
deciding it is a defect.

**The prompt grows.** Every content prompt gains a directive, on top of v2.1's
Connections constraints. Instructions compete; the QUIC finding showed a
specific instruction beating a general rule. Worth a before/after eval run on the
English path to confirm the directive does not disturb it when inactive.

---

## 6. Sequence

1. Migration + model + schemas + settings API + validation
2. `get_user_output_language`, `get_agent(output_language=...)`
3. `language_directive()` + 16 adapter insertions + prompt wording
4. Backend tests, including the metadata-prompts-excluded pair
5. `react-i18next` setup, `en`/`ru` files, provider wiring
6. Selector and toggle in `AppearanceSection`
7. Translate the surfaces listed in 3.3
8. Frontend tests
9. Full suite, then one MR to `main`

---

## 7. What changed during the build

Three deviations from the plan above, each because the code said so:

**Eighteen insertions, not sixteen.** `stream_answer` in the Anthropic and
OpenAI adapters builds its own prompt, and it is the path the chat UI actually
uses — `useStreamingChat`. Leaving it out would have given a Russian user
English chat answers whenever streaming was on, which is always.

**One query, not two.** `get_user_output_language()` alongside
`get_user_agent_config()` meant two `SELECT`s on the same `user_settings` row
at every AI call site. `get_user_ai_context()` returns both from one read. The
tests that mock an exact query sequence noticed before a human would have.

**English needs a bundle after all.** With English as the key set, the plan
assumed `en/common.json` could be empty. It cannot: `t('{{count}} course')`
with no entry renders "5 course". English carries its own plural forms.
