# Lecture audio and transcription

**Status:** exploration, nothing built. Written 2026-09-28.
**Settled 2026-09-28:** summarisation is three passes (slides → audio → reconcile),
slides authoritative. See "Summarising: three passes, not one".
**Still open for the operator:** hosted API vs local model — answered below, but
it is a privacy decision rather than a technical one.

Upload a lecture recording (or record it in the app), transcribe it, summarise it
separately from the slides, and reconcile the two into the week's summary — with
the slides authoritative and the audio adding clarification.

## The decisive finding: local transcription does not fit this box

Production hardware, measured 2026-09-28: **4 vCPU (AMD Ryzen 7 PRO 8845HS,
AVX512/VNNI), 2 GB total RAM with ~0 available, 30 GB disk at 84% used
(4.6 GB free), no GPU.**

The worker already holds torch plus `all-MiniLM-L6-v2` for embeddings (400–600 MB
RSS when warm), next to Postgres, Redis, uvicorn and two worker slots.

| faster-whisper model | RSS (int8) | Verdict on this host |
|---|---|---|
| tiny / base | 273–388 MB | Loads, then OOM territory — and at this size it *invents* plausible technical words, which is worse than no transcript for a study tool |
| **small** — first usable quality | **~1 GB** | Does not fit |
| medium | ~2.1 GB | Exceeds total system RAM on its own |

Disk compounds it: ~0.5 GB of dependencies (ffmpeg, ctranslate2, onnxruntime)
against 4.6 GB free, **plus the audio itself** — 100 lectures is 1.2 GB stored as
Opus, 4.8 GB as MP3.

Making local work means an 8 GB VM for mediocre quality, or a GPU box for good
quality. Groq runs the same `large-v3-turbo` weights for **$3.33 per 100
lectures**. The hardware never pays back. Revisit only if the deployment target
changes or a hard data-residency requirement appears.

## Cost is not the deciding factor

50-minute lecture, list prices researched 2026-09-28:

| Provider / model | Per lecture | Per 100 |
|---|---|---|
| **Groq whisper-large-v3-turbo** | **$0.033** | **$3.33** |
| AssemblyAI Universal-2 | $0.125 | $12.50 |
| OpenAI gpt-4o-mini-transcribe | $0.15 | $15 |
| OpenAI gpt-4o-transcribe | $0.30 | $30 |

Everything is $3–35 per hundred lectures. **Choose on privacy and operational
behaviour, not price.**

## Recommendation: Groq, subject to one check

Cheapest by roughly 4×, and fast enough that a 50-minute lecture occupies a
worker slot for well under a minute — which matters a great deal at
`--concurrency=2` on 4 vCPU. It runs the strongest open model for accented,
technical speech.

**Verify Groq's data-retention and training terms before committing.** Theirs are
the least clearly documented of the four. If they do not hold up, AssemblyAI at
$12.50/100 with an EU-residency endpoint is the fallback and nothing else in this
document changes.

**Deepgram is deliberately not the default**, despite the best clean-audio word
error rate: hosted requests are opted **into** its Model Improvement Program by
default, and opting out is a *per-request query parameter*. For audio containing a
lecturer's and classmates' voices, a train-by-default posture that one missed
retry path can silently undo is the wrong default.

## Transcode on ingest — it removes most of the work

**Convert to 16 kHz mono Opus as the first step.** A 50-minute lecture becomes
~12 MB, which is under *every* provider's request cap (including OpenAI's 25 MB),
and it fixes the disk budget at the same time.

One `ffmpeg` call means **no chunking code at all** — no splitting on silence, no
overlap handling, no reassembly of segment timestamps. This is the single highest
-leverage decision in the design.

## Summarising: three passes, not one

**Decided 2026-09-28.** The first draft of this proposal concatenated the
transcript extraction into the week alongside the slides and ran the existing
single `summarize` call over both. That was wrong, and the reason is worth
stating because it drives the rest of the design.

A 50-minute transcript is roughly **10× the word count of a slide deck at a
fraction of the information density** — asides, repetition, tangents, filler.
Concatenated, it swamps the deck by sheer volume, and `prompts/summarize.txt` is
tuned for slides. The likely result is that adding audio makes the summary
*worse*, which is the opposite of the point and a regression to a feature that
works today.

Instead, three separate passes:

| Pass | Prompt | Input | Output |
|---|---|---|---|
| 1. Slides | `summarize.txt` — **unchanged** | Slide extractions for the week | `source='slides'` |
| 2. Transcript | `summarize_transcript.txt` — new | Transcript extractions for the week | `source='audio'` |
| 3. Reconcile | `reconcile_summaries.txt` — new | The two summaries above | `source='final'` |

Three properties fall out of this, and they are the whole argument:

- **The existing product cannot regress.** `summarize.txt` is untouched and pass 1
  is exactly what runs today. A user who never uploads audio sees no change of any
  kind — not a reworded summary, not a different section order.
- **Each prompt faces one kind of input.** The transcript prompt can be written
  for speech (discard filler, keep worked examples and asides) without
  compromising the slide prompt.
- **The reconcile pass reasons over two short structured documents**, not one
  giant blob of mixed-density text. That is a far easier task than the one-pass
  version, and a far cheaper one in context.

### The 80/20 split, expressed so a model can follow it

A ratio is not instructable — you cannot tell a model "80/20" and get 80/20. What
*is* instructable is an asymmetry of **roles**, and that is how the reconcile
prompt should encode it:

**The slide summary is the spine.** The final summary keeps its structure,
its section order, its definitions, its formulas and its terminology. Reconcile
starts from the slide summary and extends it — it does not re-derive a summary
from two equal inputs.

**The transcript may contribute** — clarification of a slide that is terse or
cryptic; worked examples the lecturer did aloud that never reached a slide;
emphasis, explicitly flagged ("this is examinable", "this trips people up");
questions asked and answered in the room; motivation and context for why a topic
matters.

**The transcript may not** — introduce a new top-level section; restate a
definition in its own words when the slide has one; contribute anything that
merely rephrases what a slide already says; or pad a section to look thorough.

A soft budget can accompany the role rules as a hint ("expect roughly one in five
substantive points to originate in the lecture"), but the **rules are what carry
the behaviour** and the number is a nudge. Do not mistake the number for the
mechanism.

### When the two sources disagree

Slides win by default. The one exception is worth building for explicitly,
because it is common and it is exactly the value audio adds: **the lecturer
correcting their own slide.** "Ignore that figure, it should be n log n."

So the rule is: keep the slide content, and note the correction next to it rather
than silently choosing a side. A student needs to know both what the deck says —
because that is what they will see again in the exam paper — and that it was
corrected aloud.

### Provenance

Content originating in the transcript should be visibly marked — a light inline
tag, not a separate section.

**Marking it inline rather than segregating it keeps the 10-section format
intact**, so `tests/golden/test_summary_structure.py::TestPromptContract` — which
re-derives its section list from `summarize.txt` — is unaffected. A new
"From the Lecture" section would be easier to evaluate but changes the contract
and fragments the reading experience, splitting a concept from its own
clarification.

The marks also make the 80/20 *auditable*: you can read a final summary and see
at a glance whether the audio contributed insight or noise. Without them there is
no way to tell whether the reconcile prompt is working.

### Schema

`summaries` is currently unique on `(course_id, week)` — `uq_summaries_course_week`
— so three summaries per week needs a migration:

- add `source: slides | audio | final`, defaulting to `slides`
- replace the constraint with `(course_id, week, source)`
- backfill every existing row to `slides`

`version` and `source_artifacts` already exist and work per-row, so each source
versions independently for free.

### One source is a complete summary — never reconcile against nothing

**Reconcile runs only when both a `slides` and an `audio` summary exist for the
week.** With one source there is nothing to weigh, and a reconcile pass over a
single input is a paid AI call that can only degrade it.

So the published summary for a week is the first of these that exists:

1. `final` — both sources, reconciled
2. `slides` — deck only, which is every summary in the database today
3. `audio` — recording only, for a lecture with no deck, or a deck not uploaded yet

**Existing behaviour is preserved exactly**: no `final` or `audio` rows exist
today, so every read resolves to the row it resolves to now.

That rule must live in **a single accessor** in `summary_service`. Inlined at each
call site, the UI, exports, chunking and assets will drift apart — and they will
drift silently, because each one looks right in isolation.

Two consequences worth building for:

- **A `final` row can go stale.** Delete the week's last audio artifact and
  `final` still holds audio-derived content whose source is gone, and the reader
  still prefers it over `slides`. Deleting the last artifact of either source for
  a week must drop the `final` row, letting the reader fall back to the survivor.
- **The provenance marks belong to the reconcile pass, not the transcript
  summariser.** In an audio-only week every point came from the lecture, so
  marking each one is pure noise. `summarize_transcript.txt` should emit clean
  prose and reconcile should add the marks as it folds that prose into the
  spine.

### Re-runs

This makes the incremental story clean, which is the case that actually matters:
a student uploads slides during the week and the recording afterwards.

- Slides re-uploaded → `slides` bumps → `final` is stale and re-reconciles
- Audio added later → `audio` created → `final` reconciles for the first time
- Reconcile alone can be re-run after a prompt change **without re-transcribing**,
  which matters because transcription is the part that costs money

Reconcile is week-scoped rather than artifact-scoped, so it belongs outside the
per-artifact chain: a task that fires after `summarize` and returns immediately
unless both sources are present for that week. It reads two rows and writes one,
so it is idempotent by construction — and in the common slides-only case it costs
nothing at all, because it never calls the model.

### Cost

A week with **both** sources costs three summarisation calls instead of one, plus
the transcription itself. A week with one source costs exactly what it costs
today — one call — since reconcile returns without calling the model. The
up-front quota check on an audio upload has to budget for the worst case, and the
global daily ceiling should see every call.

### Testing it

The eval harness in `services/app/evals/` already has the right shape for this,
and the reconcile pass is more testable than either summariser:

- A case whose transcript **contradicts** the slides on a specific fact, with the
  slide version in `must_mention` and the transcript's version in
  `must_not_mention`. That tests slide precedence directly, and it is the single
  most valuable eval in the feature.
- A case where the transcript adds a genuinely new worked example — assert it
  survives into the final summary. The failure mode here is a reconcile prompt so
  conservative it discards everything, which would make the whole feature
  pointless while every precedence test still passed.
- The existing fabrication check already catches the reconcile pass inventing
  material present in *neither* input.

Note that `n > 1` matters more here than for the existing cases: reconcile is a
judgement task, so a single run is a weak sample.

## Five things the "just add a fourth extractor" framing hides

Beyond the summarisation restructure above:

1. **`BaseExtractor.extract()` is synchronous**, called inside a `run_async` loop.
   A hosted transcriber is async HTTP and cannot be awaited there. Needs an
   optional `aextract()` that the dispatcher prefers when present.
2. **`classify` runs *before* `extract` and reads text.** Audio has none, so the
   stage raises before transcription ever happens. The fix is to take course and
   week at upload time — and **`POST /api/uploads` has no course/week parameter
   today**. This is the largest structural change in the feature.
3. **Page refs are wrong for audio.** Slides emit `--- Page 7 ---` and
   `chunks.page_ref` records it, which is what makes a Q&A citation clickable.
   A transcript has no pages. Segments need timestamps instead, and a citation
   pointing at 34:20 of a recording is a different UI affordance from one
   pointing at a slide.
4. **`index` and `assets` cost more** — roughly 25 extra chunks per lecture,
   embedded locally on an already memory-starved box.
5. **No Celery `time_limit` is set.** A hung transcription request holds one of
   two worker slots indefinitely.

Also: **`.m4a` magic bytes sit at offset 4** (`ftyp`), so `validate_upload_content`
needs offset-aware signatures rather than the prefix match it does now.

## Credentials

Four of the five agent backends have no speech-to-text capability at all, so
transcription needs its **own credential axis** rather than riding on
`AGENT_BACKEND`.

Note the interaction: a user supplying their own agent key while transcription
stays instance-funded is exactly the shape of issue #30 — a per-user credential
that bypasses the global ceiling — and the structural guards do not catch it.
Whatever the design, transcription spend must reach `usage_records` and the
global daily ceiling.

## The largest risk is not technical

**The audio contains the lecturer and classmates — third parties who did not
consent and are not users of this app.** Some universities prohibit lecture
recording outright, and some jurisdictions require all-party consent.

This needs an explicit acknowledgement at upload ("you have permission to record
and upload this") and a clear deletion path for the source audio. It is a bigger
obstacle to shipping than any of the engineering above.

## Suggested first slice

Upload only. No in-browser recording, one provider, no chunking:

1. Audio upload endpoint with **required** course and week
2. `ffprobe` for duration → quota check → reject over a configured cap
3. Transcode to 16 kHz mono Opus
4. `TranscriptionAdapter` (Groq) → `AudioExtractor`
5. `summarize_transcript.txt` producing a `source='audio'` summary
6. `reconcile_summaries.txt` producing `source='final'`

Steps 1–4 are shippable and useful on their own: with the `source` column in
place but no reconcile stage, an audio upload produces a searchable transcript
and its own summary without touching the slide summary at all. That is a safe
place to stop and look at real output before building the reconcile pass — and
reading a few real transcript summaries is the only honest way to write the
reconcile prompt.

**Deferred:** in-browser recording — the largest piece of work and the least of
the value, since a phone already records lectures well; per-user transcription
credentials; keyterm biasing from the `concepts` table, which is a genuinely good
later idea for course-specific jargon.

## Sources

Provider pricing and model documentation, plus faster-whisper memory figures,
researched 2026-09-28. Hardware figures measured directly on the production host
the same day. Prices and terms drift — re-check before committing to a provider.
