# StudyAIO — Product, security and AI audit (2026-10-10)

**Author:** the user (founder audit; sources `findings/{product,ux,tech,security,ai,market}.md`, not in
the repo). **Logged by:** Orchestrator, 2026-10-10. The audit text in §1–§6 is the user's, reproduced
verbatim apart from formatting. The **Status** columns and §0 are the Orchestrator's, recorded the same day.

Ranking formula: `(5 - sev)*2 + conf_bonus - effort_cost`. Merged IDs list every source finding.

## 0. Status at logging time (Orchestrator)

| ID | Status 2026-10-10 | Evidence |
|---|---|---|
| SEC-00 | **Answered.** Prod api + worker: `SELF_HOSTED=false`, `AGENT_BACKEND=zai`, `ZAI_API_KEY` set (values not read). | `docker exec … printenv` via `a host shell on host shell 210`. SEC-05 is therefore **not** S1 on prod; quota checks are active (QUOTA-01 bypass is real); instance-funded chat/Q&A works on Z.ai — the "Q&A broken in prod" hypothesis is **disproved**. |
| AGENT-01 | **Partly fixed** (deployed `c28312d`, MR !34). | `claude -p` now runs with `--tools ""`, `--strict-mcp-config`, `--no-session-persistence`, an allowlisted child env (PATH, HOME, LANG, LC_ALL + auth var), Sentry frame locals off (R-027, SAFETY-053/057). **Still open:** cwd `/app`, runs as root, `--model`/`claude_model` ignored, no system prompt. Prod uses `zai`, so the CLI only runs for users who pick `claude_code` with their own credentials. |
| SEC-01 | **Open — S1.** Not touched by R-027 work. | The path is still user-settable; the CLI-sandbox fix does not cover *which binary* runs. |
| SEC-05 | Not S1 on prod (`SELF_HOSTED=false`); still the insecure default for self-hosters. | — |
| Hypothesis "host `~/.claude/settings.json` widens AGENT-01" | **Closed.** The worker no longer mounts the operator's `~/.claude`; it mounts a dedicated dir whose `settings.json` is `{}`, enforced by preflight (R-025, DEVOPS-048/059). | — |
| Open challenge "operator's personal Claude login serves tenants" | **Closed for prod** (prod uses `zai`, not `claude_code`). Remains true for any deployment that uses `claude_code` on the instance login. | — |
| R-028 (deploy race) | Being fixed (DEVOPS-060) — overlaps TECH-06 "deploy migrates without a dump". | — |

Everything else is **open** and scheduled in `docs/strategy.md` §11 M32 S4.

## 1. Verdict
- **Today it is an over-built prototype**: a feature surface comparable to funded products [unverified] (42 models, 149 routes, ~3.7k tests with 3 env-related failures), used by a handful of early users, with no usage data and no feedback loop.
- The engineering process is unusually disciplined (ADRs, safety tests, contract tests). Money and abuse paths are weak: quotas can be bypassed, cost guards are off, and one user setting lets anyone choose which program the server runs.
- The AI is the product, and its trust layer is thin. Summaries score 2–3/5 on faithfulness in the repo's own (3-case, low-n) evals and carry no citations. Q&A citation IDs can't be right, and there are no user-facing quality signals.
- The market anchor is free: NotebookLM, and a free Gemini year for regional students (sources in `findings/market.md`). For the university segment, a generic "AI study tool" is unlikely to make people pay [opinion].
- **The single biggest gap to "people would pay": no evidence of a must-have job for a specific user.** Nothing in the code or the founder facts shows retention, willingness to pay, or a segment that chose this over free tools.

## 2. S1 — fix before anything else
| ID | Title | Effort | Conf |
|---|---|---|---|
| **SEC-00** (new) | **Founder check: what prod actually runs.** `SELF_HOSTED` defaults to `True` (`config.py:132`, `.env.example:156`), and prod's value is in an untracked `.env` (`infra/deploy/deploy.sh:71-77`). If it's true, unauthenticated callers get admin on the live site (SEC-05) and all tier checks return early. Also check whether the API container has Claude credentials (`docker-compose.prod.yml:21-33` vs `:45-46`); if not, instance-funded chat/Q&A is broken. | XS | n/a |
| **SEC-01** | Any signed-in user can set `claude_code_path`; the server executes that path (verified: `settings_service.py:49-50,204-207` → `agents/factory.py:134-138` → `agents/claude_code.py:139`). Exposed on demand via `POST /api/settings/test-ai`. Precondition: argv is fixed (`-p --output-format text`, prompt on stdin), and the user needs `agent_backend=claude_code` plus syntactically valid credentials JSON, so impact depends on which binaries in the image do harm with those args. High confidence in the path, not in exploitability. | XS | high (path) |
| **AGENT-01** ← SEC-02, TECH-03, AI-11 | The Claude Code CLI runs as a full agent: default tools, no system prompt, cwd `/app` (all tenants' files), root in the worker, and the model setting is ignored. It processes untrusted lecture text, so prompt injection could pull other users' files into a summary. | S | medium |

## 3. Ranked findings
| ID | Title | Type | Sev | Effort | Conf | Lens | Score |
|---|---|---|---|---|---|---|---|
| SEC-00 | Founder check: prod `SELF_HOSTED` value + API-container AI credentials | risk | S1 | XS | n/a | red-team | 10 |
| SEC-01 | User-settable executable path (precondition noted in §2) | risk | S1 | XS | high | sec | 10 |
| AGENT-01 | CLI agent with tools on untrusted text, root, all-tenant cwd | risk | S1 | S | med | sec/tech/ai | 8 |
| AI-05 | Q&A citations come from model output: `chunk_id`/`artifact_id` can't be right (never in the prompt), `text_snippet` unchecked; chat already builds them deterministically (`qa.py:115-126`) | bug | S2 | XS | high | ai | 8 |
| QUOTA-01 ← PROD-01, PROD-02, TECH-01, SEC-04 | Plan limits/ceiling bypassed: `/uploads/batch` (UI default for 3+ files, `api/uploads.py:194-360`; rate-limited 5/min at `:207`), plus retry, reclassify, CourseOps, merge, review-resolve; `check_course_quota` has no callers. S2 while registration is closed; **S1 once public signup or Pro launches.** Moot if prod is SELF_HOSTED (checks return early, `quota_service.py:217,246,267`). | bug | S2 | S | high | prod/tech/sec | 7 |
| COST-01 ← AI-02, TECH-02 | Cost guards inert: global ceilings default 0 = off (`config.py:170-171`); CLI backend + chat/Q&A/stream record 0 tokens; concept extraction unmetered; `top_k` unbounded (`schemas.py:433`); counter lost-update race. S2 on the flat-subscription CLI backend; **S1 the day you switch to a metered API.** | risk | S2 | S | high | ai/tech | 7 |
| SEC-03 | SSRF via user-settable `ollama_base_url` / `zai_base_url` | risk | S2 | S | high | sec | 7 |
| SEC-05 | Self-hosted default: unauthenticated = admin; Postgres/Redis published. **Possible S1, pending SEC-00.** The repo does not show prod is safe: `docker-compose.prod.yml` closes the ports but doesn't set `SELF_HOSTED`. | risk | S2 | S | high | sec | 7 |
| PROD-03 | Reminders scheduled but off by default twice over; no day-2 trigger | miss | S2 | S | high | prod | 7 |
| AI-03 | 500-token chunks vs MiniLM's 256 word-piece limit: about half of each chunk is unsearchable. Worse: `chunk_size_tokens` is user-settable up to 5000 (`settings_service.py:123`). Fix needs a re-embed of existing data. | bug | S2 | S | high | ai | 7 |
| AI-04 | Streaming chat shows students raw JSON | bug | S2 | S | high | ai | 7 |
| TECH-04 | Transient AI error = permanent failure; no time limits, no recovery for stuck items | bug | S2 | M | high | tech | 6 |
| UX-01 | Pipeline progress lost when leaving the Upload page; week badge never refreshes | miss | S2 | M | high | ux | 6 |
| AI-01 (+TECH-10, AI-08) | On the API backend every task uses deprecated Opus 4 (`anthropic_api.py:27-31`, `config.py:49`); whole week re-summarized per upload; no prompt caching. ~$18/active user/mo *if* on `anthropic_api` (estimate) | risk | S2 | S | med | ai/tech | 6 |
| AI-07 | Summaries: faithfulness 2–3/5 (3 eval cases, low-n), no citations, prompt invites outside material | risk | S2 | M | high | ai | 6 |
| AI-10 | Evals: 3 summary cases, not in CI, no user feedback on AI output | miss | S2 | M | high | ai | 6 |
| SEC-06 | Users' AI keys / Claude tokens in plaintext JSONB | risk | S2 | M | high | sec | 6 |
| TECH-05 | Concurrent summarize of same week races; one artifact fails | bug | S2 | S | med | tech | 6 |
| TECH-06 | Documented auto-backup can't run in the image; deploy migrates without a dump | risk | S2 | S | med | tech | 6 |
| BILL-01 ← TECH-08, SEC-09 | Stripe webhook: no dedupe/ordering, `trialing` unmapped → paying user can be downgraded | bug | S2 | S | med | tech/sec | 6 |
| AI-06 | No relevance floor; follow-ups retrieve on the bare message | miss | S2 | S | med | ai | 6 |
| PROD-08 | Free tier too tight to show value | risk | S3 | XS | med | prod | 5 |
| UX-06 | Study hub tab bar overflows on narrow phones | bug | S3 | XS | med | ux | 5 |
| PROD-06 | New real users get no onboarding; 8 empty widgets | miss | S3 | S | high | prod | 5 |
| PROD-10 | No per-feature usage visibility, though data exists | opp | S3 | S | high | prod | 5 |
| UX-04 | Flashcard a11y: hardcoded English labels, both faces read, static hints | bug | S3 | S | high | ux | 5 |
| UX-05 | Raw server/exception strings shown to users | debt | S3 | S | high | ux | 5 |
| TECH-07 | Sync embedding blocks event loop; DB conn held across LLM calls | debt | S3 | S | high | tech | 5 |
| SEC-08 | No AI-processing disclosure/consent; emails in logs | miss | S3 | S | high | sec | 5 |
| AI-12 | 34 drifted inline prompt fallbacks; no prompt/model version on rows | debt | S3 | S | high | ai | 5 |
| PROD-04 | No shared course space; classmates each re-upload and re-pay | opp | S2 | L | med | prod | 4 |
| PROD-05 | AI flashcards/quiz items can't be edited/deleted/added | miss | S3 | M | high | prod | 4 |
| PROD-07 | No course/week picker on upload; AI-only routing | miss | S3 | S | med | prod | 4 |
| UX-02 | Dashboard reorder hover-only (no touch/keyboard) | bug | S3 | S | med | ux | 4 |
| TECH-09 | Single Celery queue for pipeline + beat jobs | debt | S3 | S | med | tech | 4 |
| SEC-07 | Vulnerable deps (starlette, python-multipart, transformers, react-router) | debt | S3 | S | med | sec | 4 |
| TECH-11 | No Python type checker; integration tier hard to run; one heavy image | debt | S3 | M | high | tech | 4 |
| PROD-11 | README advertises stub magic-link login | debt | S4 | XS | high | prod | 4 |
| UX-03 | JS animations ignore reduced-motion | debt | S4 | XS | high | ux | 4 |
| UX-08 | Non-semantic click targets; SSE JSON.parse unguarded | debt | S4 | XS | high | ux | 4 |
| SEC-10 | Rate limits per process (2× looser) | debt | S4 | XS | high | sec | 4 |
| PROD-09 | Scanned PDFs fail (no OCR); URL stores raw HTML; no video/audio | miss | S3 | M | med | prod | 3 |
| AI-09 | Heuristic JSON scraping; malformed reply fails stage with no retry | debt | S3 | M | med | ai | 3 |
| SEC-11 | Unused Terraform: plaintext secrets, Redis without auth | debt | S4 | S | high | sec | 3 |
| UX-07 | a11y e2e covers 6 routes, desktop only | risk | S4 | S | med | ux | 2 |

Merge notes:
- AI-01 and COST-01 were rated S1 by their lenses. Both are S2 here for the same reason: the default backend is `claude_code` (`config.py:52`, flat subscription), and the `anthropic_api` evidence comes from Terraform that `docs/deployment.md:199` says isn't automated. Both become S1 the day you switch to a metered API.
  - *Orchestrator note:* prod actually runs `zai` (metered API key). COST-01 and AI-01's cost argument therefore apply to prod **now**; AI-01's Opus-4 detail applies only to `anthropic_api`.
- QUOTA-01 is S2 rather than S1 because there is no revenue and fewer than 20 invited users. It is S1 before any public launch.

## 4. Quick wins (XS/S, S1–S3)
0. **SEC-00** — check prod `.env` for `SELF_HOSTED` and the API container's AI credentials. 10 minutes; it re-rates SEC-05/QUOTA-01. *(Done 2026-10-10, §0.)*
1. **SEC-01** — remove `claude_code_path` (and `claude_model` if not needed) from user `ALLOWED_KEYS`; operator-only. XS
2. **AGENT-01** — run the CLI with no tools (`--allowedTools ""` / tool-disabling flag), a temp cwd, `--model`, and non-root. S *(no tools: done; temp cwd, `--model`, non-root: open.)*
3. **AI-05** — reuse chat's deterministic citation builder in `/api/qa/ask`. XS
4. **SEC-03** — allowlist/deny private ranges for user-set base URLs (or make them operator-only in SaaS mode). S
5. **PROD-03** — turn on reminders by default for new users (opt-out), enable the global flag in prod. S
6. **AI-04** — parse before streaming, or stream plain text and attach structure at the end. S
7. **AI-03** — rechunk to about 200 tokens, cap the user setting, and re-embed (or move to an embedder with a longer context). S
8. **UX-06** — make the Study hub tab bar scroll horizontally. XS
9. **QUOTA-01 + COST-01** — fix the bypass routes and turn on non-zero ceilings, **but first decide PROD-08**: enforcing today's free limits (5 uploads, 1 course) on your only ~20 users would sabotage the retention test in §6. Suggested order: fix the bypass, set the free limits generously (or grant beta users Pro), then enforce. S

Capacity: items 0–8 are about 1–1.5 weeks at 20–30 h/week. Pause new-feature work (M32) while they're done.

## 5. Strategic opportunities
- **Trust as the wedge (AI-05, AI-07, AI-10, MKT-02):** "Every answer and summary cites your lecture slide" plus a visible faithfulness bar. NotebookLM already does grounded chat, flashcards and quizzes (market.md), so grounding alone is table stakes, not a moat. The edge would be course/week organisation plus measurably better faithfulness [unverified].
- **Weak-spot engine (AI lens differentiation, MKT-03):** the app already stores mistake history, SM-2 state and exam dates, and uses none of them for generation. Quizzes targeting weak topics, weighted by exam proximity, need data a generic chat tool doesn't collect [unverified: NotebookLM now tracks progress].
- **Shared course spaces (PROD-04):** one upload serves a whole class. It is a growth loop (invite classmates), cuts AI cost per user, and is the stepping stone to instructor/institution sales.
- **Self-host / BYO-model (MKT-01, SEC-05):** possibly a differentiator for privacy-sensitive institutions [unverified: no scan of self-hosted competitors]. Today's self-hosted defaults are insecure, so it must be hardened before being pitched.
- **Regional / Arabic (MKT-04):** only en/ru locales and no RTL in the code. Whether competitors lack Arabic is [unverified]. L effort.
- **Certification prep (market):** highest willingness to pay (Pocket Prep ~$125/yr to Schweser $1,000+; see market.md sources). It needs domain content and evals, not more features.

## 6. Hypotheses to validate
| Hypothesis | Test | Status 2026-10-10 |
|---|---|---|
| Classmates would use it weekly without being nudged | Turn on PROD-10 usage events + reminders; measure D7/D30 for the current ~20 users over 4 weeks | open |
| Students would pay over free NotebookLM | Fake-door "Pro" with the weak-spot engine + exam plan; count clicks/pre-orders among 50+ students | open |
| A shared course space drives organic invites | Seed 2 courses as shared spaces; track invites per uploader | open |
| Instructors/bootcamps want course-wide corpora | 5 instructor interviews; ask for an LOI for a one-term pilot | open |
| Prod API has no Claude credentials, so instance-funded chat/Q&A may be failing | Founder: check which `AGENT_BACKEND` prod uses and hit `/api/qa/ask` as a non-BYO user | **disproved** — prod uses `zai` with the key set in api + worker |
| Host `~/.claude/settings.json` mounted into the worker widens AGENT-01 | Inspect it; if it allows Bash/WebFetch, AGENT-01 becomes high confidence | **closed** — personal `~/.claude` no longer mounted (R-025) |
| LibreOffice preview of untrusted DOCX/PPTX can fetch external links | Check container egress and version | open |
| Concept extraction task is dead code (`pipeline/concepts_task.py:77-95`) | Confirm no dispatchers; delete | open |

## Open challenges (from red-team, unresolved)
- **Claude subscription terms.** The default backend serves many tenants from the operator's personal Claude login. That may breach Anthropic's consumer terms and is subject to per-account rate limits and suspension [unverified; check the terms]. *(Orchestrator: not the case on prod, which uses `zai`; applies to any `claude_code` instance deployment.)*
- **Copyright/IP.** Students upload instructors' slides; shared course spaces (PROD-04) would redistribute them, and instructor/B2B sales need IP consent. Not assessed.
- **Data protection.** local data-protection law / GCC data residency for course content sent to US-hosted LLMs isn't covered beyond SEC-08's consent gap [unverified; not legal advice].
- **Q&A/chat possibly broken in prod** (SEC-00): *(Orchestrator: disproved, see §0.)*
