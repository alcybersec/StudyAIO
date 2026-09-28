# Lecture audio and transcription

**Status:** exploration, nothing built. Written 2026-09-28.
**Open question for the operator:** hosted API vs local model — answered below, but
it is a privacy decision, not a technical one.

Upload a lecture recording (or record it in the app), transcribe it, and fold the
transcript into that week's summary alongside the slides.

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

## Five things the "just add a fourth extractor" framing hides

The merge path genuinely is easy: `get_week_extractions` filters only on
`course_id` and `week` with no file-type condition, `merge_extractions`
concatenates, and `generate_summary(extraction_data, existing_md)` already takes
an existing summary to update. A transcript extraction folds into the week with
**zero changes to `summarize.py`**. But:

1. **`BaseExtractor.extract()` is synchronous**, called inside a `run_async` loop.
   A hosted transcriber is async HTTP and cannot be awaited there. Needs an
   optional `aextract()` that the dispatcher prefers when present.
2. **`classify` runs *before* `extract` and reads text.** Audio has none, so the
   stage raises before transcription ever happens. The fix is to take course and
   week at upload time — and **`POST /api/uploads` has no course/week parameter
   today**. This is the largest structural change in the feature.
3. **Page-number collision.** Slides emit `--- Page 7 ---`; transcript segments
   would too, colliding in the merged text and in `chunks.page_ref`. Transcript
   segments need timestamp labels instead.
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

## Expect summaries to get worse before they get better

A transcript is roughly **10× the word count of a slide deck at much lower
information density**, full of asides, repetition and filler.
`prompts/summarize.txt` is tuned for slides. Expect to add transcript-aware
guidance — and note that `tests/golden/test_summary_structure.py::TestPromptContract`
re-derives its section list from that prompt file, so a prompt change fails the
suite until the fixture is updated too.

## Suggested first slice

Upload only. No in-browser recording, one provider, no chunking:

1. Audio upload endpoint with **required** course and week
2. `ffprobe` for duration → quota check → reject over a configured cap
3. Transcode to 16 kHz mono Opus
4. `TranscriptionAdapter` (Groq) → `AudioExtractor` → the existing merge path

**Deferred:** in-browser recording — the largest piece of work and the least of
the value, since a phone already records lectures well; per-user transcription
credentials; keyterm biasing from the `concepts` table, which is a genuinely good
later idea for course-specific jargon.

## Sources

Provider pricing and model documentation, plus faster-whisper memory figures,
researched 2026-09-28. Hardware figures measured directly on the production host
the same day. Prices and terms drift — re-check before committing to a provider.
