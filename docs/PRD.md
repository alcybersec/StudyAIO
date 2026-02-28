# StudyAIO — Product Requirements Document

> **Version:** 1.0
> **Last updated:** 2026-02-27
> **Status:** Approved for development
> **Author:** [You] + Claude (AI-assisted planning)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Product Vision & Principles](#3-product-vision--principles)
4. [What Exists Today (v0)](#4-what-exists-today-v0)
5. [v1 Scope — What We're Building](#5-v1-scope--what-were-building)
6. [Deferred Scope (v1.5+)](#6-deferred-scope-v15)
7. [Architecture](#7-architecture)
8. [Pipeline Stages](#8-pipeline-stages)
9. [AI Runtime & Agent Adapter](#9-ai-runtime--agent-adapter)
10. [Data Model](#10-data-model)
11. [Web UI — Screens & Behavior](#11-web-ui--screens--behavior)
12. [Summary Format Specification](#12-summary-format-specification)
13. [Review Inbox Specification](#13-review-inbox-specification)
14. [Q&A with Citations](#14-qa-with-citations)
15. [Study Assets — Flashcards & Quizzes](#15-study-assets--flashcards--quizzes)
16. [File Handling & Storage](#16-file-handling--storage)
17. [Idempotency Rules](#17-idempotency-rules)
18. [Docker & Infrastructure](#18-docker--infrastructure)
19. [Repo Structure](#19-repo-structure)
20. [Testing Strategy](#20-testing-strategy)
21. [Milestones & Delivery Plan](#21-milestones--delivery-plan)
22. [Definition of Done (v1)](#22-definition-of-done-v1)
23. [Risks & Mitigations](#23-risks--mitigations)
24. [Backlog (Future Ideas)](#24-backlog-future-ideas)

---

## 1. Executive Summary

StudyAIO is a local-first, fully dockerized AI study workspace that turns raw university lecture files (PDF, DOCX, PPTX) into an organized, searchable, exam-ready system. It automates the full journey from file upload to study-ready materials — summaries with embedded images, flashcards, quizzes, and a Q&A engine with source citations — while routing anything uncertain to a Review Inbox for human confirmation.

The project serves a dual purpose: it is a **real tool** the developer will use daily for their CS degree, and a **portfolio-grade** showcase of full-stack engineering, AI integration, and software architecture.

---

## 2. Problem Statement

CS students accumulate lecture materials across multiple courses in inconsistent formats (PDFs, slides, Word docs). The typical workflow is fragmented: files scattered across folders, no unified search, no automatic summarization, and study prep (flashcards, practice questions) done manually. Existing tools either require cloud upload (privacy concern), are manual and tedious, or produce shallow AI summaries with no traceability back to source material.

StudyAIO solves this by providing a single self-hosted workspace where uploading a file triggers an automated pipeline that produces organized, high-quality study materials — with every derived output traceable to its source page or slide.

---

## 3. Product Vision & Principles

### Vision

One place to upload lectures, automatically produce study materials, study with active recall, and track what you know vs. what needs work.

### Core Principles

**Automation-first, but safe.** After upload, everything runs automatically. When the system is uncertain about high-stakes decisions (course classification, week number), it creates a Review Inbox item rather than guessing silently.

**Idempotent.** Re-uploading the same file or re-running the pipeline produces an update, never a duplicate. Every operation is safe to retry.

**Evidence-first.** Every derived output (summary paragraph, flashcard, quiz question, Q&A answer) maintains a pointer back to its source: artifact ID + page/slide number + text snippet. Nothing is untraceable.

**Local-first privacy.** Runs entirely on your machine or homelab. No data leaves your network except for AI model API calls (Claude). No third-party accounts required.

**Claude Code first (v1).** The AI runtime uses Claude Code CLI (under the Max subscription) as the primary AI backend. The architecture supports adding direct API access and Ollama as future adapters without rewriting the pipeline.

**Portfolio-grade engineering.** Clean architecture, comprehensive tests, Docker reproducibility, and documentation suitable for showcasing in job applications and technical interviews.

---

## 4. What Exists Today (v0)

### Current System

A Claude Code-powered lecture management repo with two slash commands:

**`/sort_lectures`** — Scans `new_lectures/`, uses Claude Code to identify the subject code and week number from file content, moves files to `raw_lectures/<subject>/<subject>_Week#.ext` with clean naming.

**`/summarize_lectures`** — Compares `raw_lectures/` against `lectures_summary/`, finds lectures without summaries, reads/parses them, and generates comprehensive markdown summaries.

### Current Repo Structure

```
repo/
├── new_lectures/          ← Drop raw files here
├── raw_lectures/          ← Organized by course/week
│   ├── CSIT302/
│   │   ├── CSIT302_Week1.pdf
│   │   ├── CSIT302_Week1.pptx
│   │   └── CSIT302_Week2.docx
│   └── CSIT128/
│       └── ...
├── lectures_summary/      ← Generated markdown summaries
│   ├── CSIT302/
│   │   ├── CSIT302_Week1.md
│   │   └── CSIT302_Week2.md
│   └── CSIT128/
│       └── ...
└── CLAUDE.md              ← Instructions for Claude Code
```

### What v0 Does Well

- Accurate classification of course codes and week numbers from file content
- Extraction of text and images from PDF, DOCX, and PPTX files
- High-quality, detailed markdown summaries tailored to CS concepts
- Consistent folder organization

### What v0 Lacks

- No automation — requires manually running slash commands
- No database — filesystem is the only source of truth
- No web UI — CLI only
- No search or Q&A
- No flashcards, quizzes, or study assets
- No Review Inbox — Claude Code either guesses or asks interactively
- Images are extracted for context but not embedded in summaries
- No idempotency guarantees beyond filename matching

### Transition Strategy

v0's slash commands will **continue to work** alongside the new application. The v1 pipeline wraps v0's proven logic (classification, extraction, summarization) into automated Python functions that call Claude Code CLI, triggered by the web UI or file watcher instead of manual commands.

The key architectural shift is moving from **filesystem as source of truth** to **database as source of truth, filesystem as blob storage**.

---

## 5. v1 Scope — What We're Building

### In Scope

| Feature | Description |
|---|---|
| **Automated Pipeline** | Upload → classify → extract → summarize → index → generate study assets. Fully automatic, no manual steps. |
| **Web UI** | Upload files, browse courses/weeks, read summaries, view originals, resolve Review Inbox items, Q&A. |
| **Review Inbox** | System queues uncertain decisions for human resolution. Pipeline continues without blocking. |
| **Q&A with Citations** | Ask questions scoped to a course, a week, or across all courses. Answers include page/slide citations. |
| **Basic Flashcards** | Auto-generated Q&A cards from lecture content. Simple deck flip-through (no spaced repetition). |
| **Basic Quizzes** | Auto-generated multiple choice and short answer questions from lecture content. |
| **Image Embedding** | Extracted images from lectures are embedded in markdown summaries. |
| **Idempotent Re-processing** | Re-uploading the same file updates existing records; no duplicates. |
| **Claude Code Slash Commands** | Existing `/sort_lectures` and `/summarize_lectures` remain functional. |
| **Docker Compose Deployment** | Entire stack runs via `docker compose up`. |

### Out of Scope (v1)

| Feature | Rationale |
|---|---|
| Exam Mode (scheduling, weak-topic adaptation) | Complex feature; build after core pipeline is solid. |
| CourseOps (deadline extraction, calendar export) | Depends on structured course outline parsing; add after v1. |
| Spaced Repetition (SM-2 algorithm) | v1 flashcards are simple decks; SRS added when usage data exists. |
| Ollama / Local Model Support | Adapter interface designed in; implementation deferred. |
| Direct Anthropic API Adapter | Designed in; v1 uses Claude Code CLI exclusively. |
| Multi-user / Authentication | Single user; no auth needed. |
| Mobile PWA | UI will be responsive but not installable offline. |
| MinIO Object Storage | Docker volumes are sufficient for v1 scale. |

---

## 6. Deferred Scope (v1.5+)

### v1.5 — Exam Mode

- Define exam date and topic scope
- Auto-generate a study schedule with daily sessions
- Flashcards with spaced repetition (SM-2 or similar)
- Quiz-based weak topic detection and adaptive scheduling
- Progress tracking and streak mechanics

### v1.5 — CourseOps

- Upload course outlines, rubrics, tutorial sheets
- Extract deadlines, assessment weights, deliverables
- Export to `calendar.ics` and markdown task plan
- Optional GitHub Issues export

### v2 — Agent Adapters

- Direct Anthropic API adapter (cleaner, pay-per-token)
- Ollama adapter for fully local AI (no external API calls)
- Model routing: cheap model for extraction/flashcards, powerful model for summarization/Q&A

### v2+ — Integrations & UX

- Obsidian markdown export
- "I have 45 minutes" session generator
- Lecture diff on re-upload
- Canvas iCal merge
- Duplicate detection and merge suggestions

---

## 7. Architecture

### Approach: Modular Monolith

A single Python application with clear internal module boundaries, a Celery task queue for background processing, and a React frontend — all orchestrated by Docker Compose.

This gives the architectural clarity of microservices (clean boundaries, independent scaling potential) without the operational overhead of inter-service communication, distributed debugging, and shared schema packages.

### System Components

```
┌─────────────────────────────────────────────────────────┐
│                     Docker Compose                       │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ React UI │  │ FastAPI   │  │ Celery   │  │ Claude │ │
│  │ (Vite)   │──│ Server    │──│ Worker   │──│ Code   │ │
│  │ :3000    │  │ :8000     │  │          │  │ CLI    │ │
│  └──────────┘  └────┬─────┘  └────┬─────┘  └────────┘ │
│                     │              │                     │
│              ┌──────┴──────────────┴──────┐             │
│              │                            │             │
│         ┌────┴─────┐              ┌───────┴──┐         │
│         │ Postgres │              │  Redis   │         │
│         │ +pgvector│              │  :6379   │         │
│         │ :5432    │              └──────────┘         │
│         └──────────┘                                   │
│                                                         │
│         ┌──────────────────────────┐                   │
│         │  Docker Volumes          │                   │
│         │  ./data/uploads          │                   │
│         │  ./data/extractions      │                   │
│         │  ./data/summaries        │                   │
│         └──────────────────────────┘                   │
└─────────────────────────────────────────────────────────┘
```

### Component Responsibilities

**React UI (Vite, port 3000)** — Single-page application. Upload files, browse courses/weeks, read summaries, flip flashcards, take quizzes, resolve Review Inbox items, ask Q&A questions. Responsive layout for desktop; functional on mobile as a nice-to-have.

**FastAPI Server (port 8000)** — REST API. Handles file uploads, serves course/week/summary data, manages Review Inbox CRUD, proxies Q&A requests, provides WebSocket or SSE for pipeline progress updates.

**Celery Worker** — Executes pipeline stages as chained tasks. Calls Claude Code CLI for AI operations (classification, summarization, flashcard/quiz generation, Q&A). Creates Review Items when confidence is low. Multiple workers can run in parallel for throughput.

**Claude Code CLI** — The AI backend for v1. Invoked by the Celery worker via subprocess. Uses the Max subscription's shared usage pool. Handles: course/week classification, text summarization, flashcard generation, quiz generation, question answering.

**Postgres + pgvector (port 5432)** — Primary data store. All entities (courses, artifacts, summaries, chunks, flashcards, etc.) plus vector embeddings for semantic search and Q&A retrieval.

**Redis (port 6379)** — Celery task broker and result backend. Optional caching layer for frequently accessed data.

**Docker Volumes** — Persistent storage for uploaded files, extracted content, and generated summaries. Mounted from `./data/` on the host.

### Internal Module Boundaries

Within the Python application, code is organized into clear modules:

```
app/
├── api/           # FastAPI routes and request/response schemas
├── pipeline/      # Pipeline stage definitions and orchestration
├── agents/        # Agent adapter interface + Claude Code implementation
├── models/        # SQLAlchemy ORM models
├── services/      # Business logic (courses, summaries, flashcards, search)
├── extractors/    # File parsing (PDF, DOCX, PPTX)
└── core/          # Config, database setup, shared utilities
```

### Request Flow

1. User uploads a file via React UI
2. FastAPI receives the file, saves to Docker volume, creates `LectureArtifact` record in Postgres
3. FastAPI enqueues a pipeline job to Redis
4. Celery worker picks up the job and executes the pipeline stages in sequence
5. For AI steps, the worker invokes Claude Code CLI via subprocess
6. Results are persisted to Postgres; files written to Docker volumes
7. If confidence is low at any stage, a `ReviewItem` is created and the pipeline continues (or pauses that branch)
8. FastAPI serves the results; React UI polls or receives updates via SSE
9. User can resolve Review Items in the UI, which may trigger re-processing of affected stages

---

## 8. Pipeline Stages

The pipeline runs as a Celery task chain. Each stage is an independent, retryable task. If a stage fails, it can be retried without re-running previous stages.

### Stage 0: Ingest

**Trigger:** File upload via UI or file watcher detecting a new file in `new_lectures/`.

**Actions:**
- Compute SHA-256 hash of the file
- Check if this hash already exists in the database (idempotency check)
- If new: save file to `data/uploads/<original_name>_<hash_prefix>.<ext>`, create `LectureArtifact` record
- If duplicate: skip ingest, return existing artifact ID
- Enqueue Stage 1

**Output:** `LectureArtifact` record with `status: ingested`

### Stage 1: Classify

**Trigger:** Successful ingest.

**Actions:**
- Extract first few pages of text (lightweight, no full extraction yet)
- Send to Claude Code with classification prompt: identify course code, week number, lecture title
- Apply rule-based heuristics as fallback (filename patterns, known course codes)
- If confidence ≥ threshold: update `LectureArtifact` with `course_id`, `week`, `title`
- If confidence < threshold: create `ReviewItem` with type `classification`, suggested values, and extracted context

**Confidence rules:**
- Course code found in filename AND content → high confidence
- Course code found in content only → medium confidence (proceed, but flag)
- Course code not found → low confidence → Review Item
- Week number ambiguous or missing → Review Item

**Output:** `LectureArtifact` updated with classification OR `ReviewItem` created

**On Review resolution:** When user resolves the Review Item, the artifact is updated and downstream stages are triggered.

### Stage 2: Extract

**Trigger:** Successful classification (or Review Item resolved).

**Actions:**
- Full extraction based on file type:
  - **PDF:** Extract per-page text + embedded images with page mapping
  - **DOCX:** Extract text by section + embedded images
  - **PPTX:** Extract per-slide text + speaker notes + embedded images with slide mapping
- Produce an extraction manifest (JSON) describing all extracted content and source mappings
- Save extracted images to `data/extractions/<artifact_id>/images/`
- Create `Extraction` record with manifest

**Output:** `Extraction` record, extracted images on disk, manifest JSON

### Stage 3: Summarize

**Trigger:** Successful extraction.

**Actions:**
- Check if a `Summary` already exists for this course + week
  - If yes: pass existing summary + new extraction to Claude Code for an **update** (idempotent merge)
  - If no: generate a new summary from extraction
- Summary follows the [Summary Format Specification](#12-summary-format-specification)
- Embed relevant extracted images in the markdown (as relative paths)
- Save markdown to `data/summaries/<course_code>/<course_code>_Week<N>.md`
- Create or update `Summary` record with incremented version

**Output:** `Summary` record (new or updated), markdown file on disk

### Stage 4: Index

**Trigger:** Successful extraction (runs in parallel with Stage 3).

**Actions:**
- Split extracted text into chunks with stable IDs (based on artifact + page + position)
- Each chunk retains a reference to its source: `artifact_id`, `page/slide number`, `text snippet`
- Generate embeddings for each chunk (via Claude Code or a local embedding model)
- Store chunks in `Chunk` table with embeddings in pgvector
- If chunk already exists (same stable ID), update rather than duplicate

**Output:** `Chunk` records with embeddings in Postgres

### Stage 5: Study Assets

**Trigger:** Successful summarization.

**Actions:**
- Send summary + extraction to Claude Code with flashcard generation prompt
- Generate flashcards (front/back Q&A pairs) tagged by course, week, and topic
- Send summary + extraction to Claude Code with quiz generation prompt
- Generate quiz questions (multiple choice + short answer) with answers and explanations
- Each flashcard and quiz question includes a source reference (artifact + page/slide)
- Store in `Flashcard` and `QuizQuestion` tables
- Idempotency: regenerating for the same course+week replaces existing assets (versioned)

**Output:** `Flashcard` and `QuizQuestion` records

### Stage 6: Finalize

**Trigger:** All previous stages complete.

**Actions:**
- Update `LectureArtifact` status to `processed`
- Update course-level statistics (total lectures, weeks covered, etc.)
- Log pipeline completion with timing metrics

**Output:** Pipeline complete, artifact fully processed

### Pipeline State Machine

```
ingested → classifying → classified → extracting → extracted
                ↓                                      ↓
          review_pending                         summarizing + indexing
                ↓                                      ↓
          (user resolves)                    generating_assets
                ↓                                      ↓
          classified (resume)                    processed
```

---

## 9. AI Runtime & Agent Adapter

### Interface Design

The agent adapter provides a clean interface that all AI operations go through. v1 implements Claude Code CLI; the interface is designed so future adapters (Anthropic API, Ollama) can be added without changing the pipeline.

```python
class AgentAdapter(ABC):
    """Abstract interface for AI operations."""

    @abstractmethod
    async def classify_lecture(
        self, text_preview: str, filename: str, known_courses: list[str]
    ) -> ClassificationResult:
        """Identify course code, week number, and lecture title."""
        ...

    @abstractmethod
    async def generate_summary(
        self, extraction: ExtractionData, existing_summary: str | None
    ) -> SummaryResult:
        """Generate or update a lecture summary."""
        ...

    @abstractmethod
    async def generate_flashcards(
        self, summary: str, extraction: ExtractionData, count: int
    ) -> list[Flashcard]:
        """Generate flashcard Q&A pairs."""
        ...

    @abstractmethod
    async def generate_quiz(
        self, summary: str, extraction: ExtractionData, count: int
    ) -> list[QuizQuestion]:
        """Generate quiz questions (MCQ + short answer)."""
        ...

    @abstractmethod
    async def answer_question(
        self, question: str, context_chunks: list[Chunk]
    ) -> AnswerResult:
        """Answer a question using retrieved context chunks."""
        ...
```

### v1 Implementation: Claude Code CLI Adapter

```python
class ClaudeCodeAdapter(AgentAdapter):
    """Calls Claude Code CLI via subprocess."""

    async def classify_lecture(self, text_preview, filename, known_courses):
        prompt = self._build_classification_prompt(text_preview, filename, known_courses)
        result = await self._run_claude_code(prompt)
        return self._parse_classification(result)

    async def _run_claude_code(self, prompt: str) -> str:
        """Execute claude CLI with the given prompt and return output."""
        process = await asyncio.create_subprocess_exec(
            "claude", "-p", prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise AgentError(f"Claude Code failed: {stderr.decode()}")
        return stdout.decode()
```

### Future Adapters (Designed In, Not Implemented)

**AnthropicAPIAdapter** — Calls the Anthropic API directly via the Python SDK. Cleaner than shelling out. Billed per token (separate from Max plan). Would support model routing (Sonnet for cheap tasks, Opus for complex ones).

**OllamaAdapter** — Calls a local Ollama instance. Fully offline, no API costs. Quality depends on model choice. Suitable for extraction and simple tasks; may not match Claude quality for summarization.

### Prompt Management

All prompts live in a `prompts/` directory as versioned text/Jinja2 templates:

```
prompts/
├── classify.txt
├── summarize.txt
├── summarize_update.txt
├── flashcards.txt
├── quiz.txt
├── answer_question.txt
└── README.md
```

This allows prompt iteration without code changes, and makes prompt versions trackable in git.

---

## 10. Data Model

### Entity Relationship Overview

```
Course 1──* LectureArtifact 1──1 Extraction
  │                │
  │                ├──* Chunk (with embedding)
  │                │
  ├──* Summary     ├──* Flashcard
  │   (per week)   │
  │                └──* QuizQuestion
  ├──* DeadlineTask (v1.5)
  │
  └──* StudyBlock (v1.5)

ReviewItem (standalone, references any entity)
```

### Table Definitions

#### Course

| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| code | VARCHAR(20) | e.g., "CSIT302". Unique. |
| name | VARCHAR(255) | Full course name, nullable (can be added later) |
| term | VARCHAR(50) | e.g., "2026-S1", nullable |
| created_at | TIMESTAMP | Auto-set |
| updated_at | TIMESTAMP | Auto-updated |

#### LectureArtifact

| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| course_id | UUID | FK → Course, nullable until classified |
| week | INTEGER | Nullable until classified |
| title | VARCHAR(500) | Nullable until classified |
| original_filename | VARCHAR(500) | Original upload name |
| file_path | VARCHAR(1000) | Path in Docker volume |
| file_type | VARCHAR(10) | "pdf", "docx", "pptx" |
| sha256 | VARCHAR(64) | File hash. Unique. |
| file_size_bytes | BIGINT | |
| status | VARCHAR(30) | See pipeline states |
| pipeline_started_at | TIMESTAMP | Nullable |
| pipeline_completed_at | TIMESTAMP | Nullable |
| created_at | TIMESTAMP | Auto-set |
| updated_at | TIMESTAMP | Auto-updated |

#### Extraction

| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| artifact_id | UUID | FK → LectureArtifact. Unique (1:1). |
| manifest_json | JSONB | Describes extracted content structure |
| image_count | INTEGER | Number of extracted images |
| page_count | INTEGER | Total pages/slides |
| extraction_path | VARCHAR(1000) | Path to extraction directory |
| created_at | TIMESTAMP | Auto-set |

Manifest JSON structure:
```json
{
  "pages": [
    {
      "page_number": 1,
      "text": "...",
      "images": [
        {"filename": "page1_img1.png", "caption": "...", "position": "top"}
      ]
    }
  ],
  "metadata": {
    "extractor_version": "1.0",
    "source_type": "pdf"
  }
}
```

#### Summary

| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| course_id | UUID | FK → Course |
| week | INTEGER | |
| content_md | TEXT | Full markdown content |
| file_path | VARCHAR(1000) | Path to .md file on disk |
| version | INTEGER | Incremented on each update |
| source_artifacts | JSONB | Array of artifact IDs that contributed |
| created_at | TIMESTAMP | Auto-set |
| updated_at | TIMESTAMP | Auto-updated |

Unique constraint on `(course_id, week)`.

#### Chunk

| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| artifact_id | UUID | FK → LectureArtifact |
| stable_id | VARCHAR(255) | Deterministic ID for idempotency. Unique. |
| text | TEXT | Chunk text content |
| page_ref | INTEGER | Source page/slide number |
| slide_title | VARCHAR(500) | Slide/section title, nullable |
| embedding | VECTOR(1536) | pgvector column, nullable |
| created_at | TIMESTAMP | Auto-set |

`stable_id` format: `<artifact_sha256_prefix>_p<page>_c<chunk_index>`

#### Flashcard

| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| course_id | UUID | FK → Course |
| week | INTEGER | |
| front | TEXT | Question side |
| back | TEXT | Answer side |
| tags | JSONB | Array of topic tags |
| source_artifact_id | UUID | FK → LectureArtifact |
| source_page_ref | INTEGER | Source page/slide |
| generation_version | INTEGER | For idempotent regeneration |
| created_at | TIMESTAMP | Auto-set |

#### QuizQuestion

| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| course_id | UUID | FK → Course |
| week | INTEGER | |
| question_type | VARCHAR(20) | "multiple_choice" or "short_answer" |
| question | TEXT | The question text |
| options_json | JSONB | For MCQ: array of option strings. Null for short answer. |
| correct_answer | TEXT | Correct answer text |
| explanation | TEXT | Why this answer is correct |
| source_artifact_id | UUID | FK → LectureArtifact |
| source_page_ref | INTEGER | Source page/slide |
| generation_version | INTEGER | For idempotent regeneration |
| created_at | TIMESTAMP | Auto-set |

#### ReviewItem

| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| review_type | VARCHAR(50) | e.g., "classification", "week_ambiguous", "date_confidence" |
| entity_type | VARCHAR(50) | Which entity this relates to (e.g., "lecture_artifact") |
| entity_id | UUID | ID of the related entity |
| payload_json | JSONB | Context for the reviewer (see spec below) |
| suggested_values | JSONB | System's best guesses |
| status | VARCHAR(20) | "pending", "resolved", "dismissed" |
| resolution_json | JSONB | What the user chose, nullable |
| created_at | TIMESTAMP | Auto-set |
| resolved_at | TIMESTAMP | Nullable |

#### PipelineRun

| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| artifact_id | UUID | FK → LectureArtifact |
| stage | VARCHAR(30) | Current/completed stage name |
| status | VARCHAR(20) | "running", "completed", "failed", "waiting_review" |
| error_message | TEXT | Nullable |
| started_at | TIMESTAMP | |
| completed_at | TIMESTAMP | Nullable |
| duration_ms | INTEGER | Nullable |

### Indexes

- `LectureArtifact.sha256` — unique index for dedup
- `Chunk.stable_id` — unique index for idempotency
- `Chunk.embedding` — pgvector index (ivfflat or hnsw) for similarity search
- `Summary(course_id, week)` — unique index
- `ReviewItem.status` — partial index on `status = 'pending'` for inbox queries
- `Flashcard(course_id, week)` — for filtered retrieval
- `QuizQuestion(course_id, week)` — for filtered retrieval

---

## 11. Web UI — Screens & Behavior

### Technology

- **Framework:** React with Vite
- **Styling:** Tailwind CSS (utility-first, responsive)
- **State management:** React Query (TanStack Query) for server state
- **Routing:** React Router
- **Markdown rendering:** react-markdown with remark plugins
- **PDF viewing:** react-pdf or pdf.js
- **Real-time updates:** Server-Sent Events (SSE) from FastAPI for pipeline progress

### Design Direction

The UI should feel like a modern productivity tool — clean, spacious, and minimal. Think Notion or Linear rather than a dashboard covered in charts. Neutral color palette with a single accent color. Good typography (Inter or similar). Generous whitespace. Responsive by default via Tailwind breakpoints.

A detailed UI/UX design phase should precede frontend implementation. The screen descriptions below define functionality and information architecture, not visual design.

### Screen: Dashboard

**URL:** `/`

**Purpose:** At-a-glance view of what's happening and what needs attention.

**Content:**
- **Review Inbox count** — prominent badge if items are pending; links to Review Inbox
- **Recent activity** — last 5 pipeline completions (e.g., "CSIT302 Week 3 summary updated")
- **Courses overview** — cards for each course showing: code, name, weeks covered (e.g., "7/10"), last updated
- **Quick upload** — drag-and-drop zone or button to upload a file immediately

**Responsive:** Cards stack vertically on narrow screens. Upload zone remains accessible.

### Screen: Course Page

**URL:** `/courses/:courseCode`

**Purpose:** Everything for one course.

**Content:**
- Course header (code, name, term)
- Weeks list — each week shows: week number, lecture title(s), summary status (✓ generated / ⏳ processing / ❌ missing), flashcard count, quiz count
- Click a week → navigates to Week View
- "Upload to this course" button

**Responsive:** Weeks list as full-width rows on mobile.

### Screen: Week View

**URL:** `/courses/:courseCode/weeks/:weekNumber`

**Purpose:** The main study screen for a single week.

**Content (desktop — split layout):**
- **Left panel:** Original file viewer (PDF viewer for PDFs, rendered content for DOCX/PPTX) with page/slide navigation
- **Right panel:** Tabbed interface:
  - **Summary** — rendered markdown with embedded images
  - **Flashcards** — card deck with flip interaction
  - **Quiz** — take a quiz with scoring
  - **Q&A** — ask a question scoped to this week; answer includes citations linking to the left panel

**Content (mobile — stacked layout):**
- Tabs at top: Summary | Flashcards | Quiz | Q&A
- Original file accessible via a "View Original" button/modal

### Screen: Q&A

**URL:** `/qa` (global) or inline on Week View (scoped)

**Purpose:** Ask questions and get answers with source citations.

**Content:**
- Text input for question
- Scope selector: "All courses" / specific course / specific week
- Answer display with inline citations: `[CSIT302 Week 3, Slide 14]`
- Each citation is clickable → opens the source file at the referenced page/slide
- Answer history (recent questions in this session)

### Screen: Review Inbox

**URL:** `/review`

**Purpose:** Resolve items the system couldn't confidently handle.

**Content:**
- List of pending Review Items, newest first
- Each item shows: type, context excerpt, system's suggestions, action buttons
- Resolution actions:
  - Select from suggested options (one-click)
  - Enter custom value
  - Dismiss (ignore this item)
- After resolution, pipeline resumes for affected artifact

**Responsive:** Designed for quick tap-through on mobile. Large touch targets.

### Screen: Upload

**URL:** `/upload` or modal overlay

**Purpose:** Upload one or multiple files.

**Content:**
- Drag-and-drop zone (accepts PDF, DOCX, PPTX)
- File list with upload progress
- Optional: pre-select course (if known)
- After upload: shows pipeline progress for each file (SSE updates)

### Navigation

- Sidebar on desktop (collapsible): Dashboard, Courses (expandable), Q&A, Review Inbox, Upload
- Bottom tab bar on mobile: Dashboard, Courses, Q&A, Review (with badge), Upload

---

## 12. Summary Format Specification

Summaries are the primary study artifact. They must be consistent, comprehensive, and structured for both human reading and machine re-processing (idempotency).

### Required Sections

Every week summary must include these sections in order:

```markdown
# <Course Code> — Week <N>: <Topic Title>

## Key Concepts

<Paragraph or structured explanation of the week's main concepts.
Each concept should be explained clearly enough to understand
without referring back to slides.>

## Definitions

| Term | Definition |
|---|---|
| <term> | <clear definition in context of this course> |

## Code Examples

<If applicable. Reproduce and explain key code examples from the lecture.
Include the language, what it demonstrates, and why it matters.>

```<language>
<code>
```

**Explanation:** <what this code does and why it's important>

## Diagrams & Figures

<Embedded images from the lecture with descriptions.>

![<caption>](<relative_path_to_image>)

**Figure <N>:** <description of what this diagram shows and why it matters>

## Potential Exam Topics

- <topic 1>: <why it's likely to be examined, what to focus on>
- <topic 2>: ...

## Summary

<2-3 paragraph high-level summary of the week's content,
connecting concepts to the broader course narrative.>

---
*Generated by StudyAIO v1 | Sources: <artifact_id(s)> | Version: <N>*
```

### Idempotency Rules for Summaries

- A summary is uniquely identified by `(course_id, week)`
- If a new artifact is uploaded for the same course + week, the summary is **regenerated** incorporating all artifacts for that week
- The regeneration prompt includes the existing summary to preserve quality and avoid information loss
- The `version` field is incremented on each update
- The `source_artifacts` JSONB array tracks which artifacts contributed

### Image Embedding Rules

- Images are embedded using relative markdown paths: `![caption](../../data/extractions/<artifact_id>/images/<filename>)`
- The FastAPI server serves these images via a static file route
- Only images that are contextually relevant to the summary content should be embedded (decided by Claude during summarization)
- Each image must have a caption and a descriptive paragraph

---

## 13. Review Inbox Specification

### When Review Items Are Created

| Situation | Review Type | Payload |
|---|---|---|
| Course code not found in file | `classification_course` | Text excerpt, filename, suggested courses |
| Week number ambiguous | `classification_week` | Text excerpt, filename, suggested weeks |
| Multiple possible course matches | `classification_ambiguous` | Text excerpt, candidate matches with confidence scores |
| File appears to be a duplicate but content differs | `duplicate_conflict` | Both artifact IDs, diff summary |

### Payload Structure

```json
{
  "context": "Extracted text from first 2 pages...",
  "filename": "Lecture5_Networks.pdf",
  "suggestions": [
    {"value": {"course": "CSIT302", "week": 5}, "confidence": 0.7},
    {"value": {"course": "CSIT115", "week": 5}, "confidence": 0.3}
  ],
  "reason": "Course code not found in filename or content. Best guess based on topic similarity."
}
```

### Resolution Flow

1. User opens Review Inbox (web UI or CLI)
2. Sees the context, system suggestions, and reason
3. Either: selects a suggestion, enters a custom value, or dismisses
4. On resolution:
   - `ReviewItem.status` → `resolved`
   - `ReviewItem.resolution_json` stores the chosen value
   - `ReviewItem.resolved_at` is set
   - The pipeline resumes: the artifact is updated with the resolved classification and downstream stages are triggered

### Non-blocking Behavior

The pipeline does **not** halt entirely when a Review Item is created. Behavior:
- The affected artifact is set to `status: waiting_review`
- Other files in the same upload batch continue processing normally
- When the review is resolved, a new pipeline job is enqueued for the affected artifact starting from the stage after classification

---

## 14. Q&A with Citations

### How It Works

1. User submits a question with a scope (all courses / specific course / specific week)
2. FastAPI receives the question and the scope filter
3. The question is embedded (via Claude Code or a lightweight embedding model)
4. pgvector similarity search retrieves the top-K relevant chunks, filtered by scope
5. The chunks (with their source references) are sent to Claude Code along with the question
6. Claude generates an answer and is instructed to cite sources using a specific format
7. The answer is returned with structured citation objects

### Citation Format

Claude is prompted to use inline citation markers like `[1]`, `[2]`, etc. The response includes both the answer text and a structured citations array:

```json
{
  "answer": "Binary search trees maintain sorted order by ensuring that for every node, all values in the left subtree are smaller [1]. The worst-case time complexity is O(n) when the tree degenerates into a linked list [2].",
  "citations": [
    {
      "ref": 1,
      "artifact_id": "uuid-abc",
      "course_code": "CSIT302",
      "week": 3,
      "page": 14,
      "snippet": "For every node in a BST, all keys in the left subtree..."
    },
    {
      "ref": 2,
      "artifact_id": "uuid-def",
      "course_code": "CSIT302",
      "week": 3,
      "page": 16,
      "snippet": "In the worst case, a BST degenerates into a linked list..."
    }
  ]
}
```

### UI Behavior

- Citation markers in the answer are rendered as clickable links
- Clicking a citation opens the original file at the referenced page/slide (in a side panel or modal)
- The relevant snippet is highlighted in the source view if possible

---

## 15. Study Assets — Flashcards & Quizzes

### Flashcards (v1)

**Generation:** After summarization, Claude Code generates flashcards from the summary and extraction data. Each flashcard has a front (question), back (answer), topic tags, and a source reference.

**Target count:** 10-20 flashcards per week (configurable).

**UI behavior:**
- Card deck interface: shows front, user taps/clicks to reveal back
- Navigate: next, previous, shuffle
- No scoring or SRS in v1 — just a study tool

**Regeneration:** Flashcards for a course+week are regenerated (replaced) when the summary is updated. `generation_version` tracks this.

### Quizzes (v1)

**Generation:** Claude Code generates quiz questions from the summary and extraction data.

**Question types:**
- **Multiple choice (MCQ):** 4 options, one correct. Includes explanation of correct answer.
- **Short answer:** Open text question. Includes model answer and key points for self-assessment.

**Target count:** 5-10 questions per week (configurable), mix of both types.

**UI behavior:**
- Present questions one at a time
- MCQ: radio buttons, submit, show correct/incorrect + explanation
- Short answer: text area, submit, show model answer for self-comparison
- Score summary at the end

**Regeneration:** Same as flashcards — replaced on summary update.

---

## 16. File Handling & Storage

### Upload Flow

1. File received by FastAPI (multipart upload)
2. SHA-256 hash computed
3. Dedup check against `LectureArtifact.sha256`
4. File saved to `data/uploads/<sha256_prefix_8>_<sanitized_original_name>.<ext>`
5. Artifact record created in database

### Volume Structure

```
data/
├── uploads/           # Raw uploaded files (never modified)
│   ├── a1b2c3d4_CSIT302_Week3.pdf
│   └── e5f6g7h8_CSIT128_Lecture5.pptx
├── extractions/       # Extracted content per artifact
│   ├── <artifact_uuid>/
│   │   ├── manifest.json
│   │   ├── text/
│   │   │   ├── page_001.txt
│   │   │   └── page_002.txt
│   │   └── images/
│   │       ├── page1_img1.png
│   │       └── page3_img2.png
│   └── ...
└── summaries/         # Generated markdown summaries
    ├── CSIT302/
    │   ├── CSIT302_Week1.md
    │   └── CSIT302_Week2.md
    └── CSIT128/
        └── ...
```

### Serving Files in the UI

FastAPI serves files from the data volumes via static file routes:
- `/files/uploads/<path>` — original files
- `/files/extractions/<path>` — extracted content
- `/files/summaries/<path>` — summary markdown files
- PDF viewing uses pdf.js pointed at the upload path

### Compatibility with v0

The existing `raw_lectures/` and `lectures_summary/` directories from v0 can be **imported** into StudyAIO via a migration script that:
1. Scans `raw_lectures/` for organized files
2. Creates `Course` and `LectureArtifact` records from the folder structure
3. Copies files to the `data/uploads/` volume
4. Links existing summaries in `lectures_summary/` to `Summary` records
5. Runs extraction + indexing stages on imported artifacts

---

## 17. Idempotency Rules

### File Level

- **Same file uploaded twice** (identical SHA-256): second upload is a no-op. Returns existing artifact.
- **Updated version of a file** (same course+week, different SHA-256): new artifact created, summary regenerated incorporating both artifacts, old flashcards/quizzes replaced.

### Summary Level

- **Same course+week, new artifact**: summary is regenerated (not duplicated). Version incremented.
- **Re-running summarization** without new data: produces the same output (same version).
- **Multiple artifacts per week**: summary incorporates all artifacts for that week.

### Index Level

- Chunks use stable IDs derived from `(artifact_sha256_prefix, page, chunk_position)`.
- Re-indexing the same artifact produces identical chunk IDs → upsert, not insert.

### Study Assets Level

- Flashcards and quizzes are regenerated per course+week when the summary changes.
- Old assets are replaced (soft delete or hard delete + recreate).
- `generation_version` tracks which version of the summary produced the current assets.

### Review Items

- If a Review Item already exists for an artifact, a duplicate is not created.
- Resolving a Review Item triggers downstream processing exactly once.

---

## 18. Docker & Infrastructure

### Docker Compose Services

```yaml
services:
  ui:
    build: ./services/ui
    ports: ["3000:3000"]
    depends_on: [api]

  api:
    build: ./services/app
    ports: ["8000:8000"]
    depends_on: [db, redis]
    volumes:
      - ./data:/app/data
    environment:
      - DATABASE_URL=postgresql://studyaio:studyaio@db:5432/studyaio
      - REDIS_URL=redis://redis:6379/0

  worker:
    build: ./services/app
    command: celery -A app.worker worker --loglevel=info
    depends_on: [db, redis]
    volumes:
      - ./data:/app/data
    environment:
      - DATABASE_URL=postgresql://studyaio:studyaio@db:5432/studyaio
      - REDIS_URL=redis://redis:6379/0

  db:
    image: pgvector/pgvector:pg16
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./infra/db/init.sql:/docker-entrypoint-initdb.d/init.sql
    environment:
      - POSTGRES_USER=studyaio
      - POSTGRES_PASSWORD=studyaio
      - POSTGRES_DB=studyaio

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  redisdata:
```

### Environment Configuration

All configuration via environment variables with sensible defaults:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | (required) | Postgres connection string |
| `REDIS_URL` | (required) | Redis connection string |
| `DATA_DIR` | `/app/data` | Root path for file storage |
| `CLAUDE_CODE_PATH` | `claude` | Path to Claude Code CLI binary |
| `CLAUDE_MODEL` | `opus` | Model preference for Claude Code |
| `CLASSIFICATION_CONFIDENCE_THRESHOLD` | `0.7` | Below this → Review Item |
| `FLASHCARD_COUNT_PER_WEEK` | `15` | Target flashcards per week |
| `QUIZ_QUESTION_COUNT_PER_WEEK` | `8` | Target quiz questions per week |
| `CHUNK_SIZE_TOKENS` | `500` | Target size for index chunks |
| `CHUNK_OVERLAP_TOKENS` | `50` | Overlap between chunks |

### Development vs Production

**Dev (`docker compose up`):**
- Hot reload for FastAPI (uvicorn --reload)
- Vite dev server with HMR for React
- Postgres data persisted in Docker volume
- Exposed ports for direct access

**Prod-ish (`docker compose -f docker-compose.yml -f docker-compose.prod.yml up`):**
- Built/optimized images
- Nginx reverse proxy in front of API + UI
- No exposed database port
- Health checks on all services

### Claude Code in Docker

The Celery worker container needs Claude Code CLI installed and authenticated. Options:

1. **Mount the host's Claude Code auth** — Mount `~/.claude/` into the worker container. Claude Code uses the host's Max plan authentication.
2. **Install Claude Code in the worker image** — Include `claude` in the Dockerfile and authenticate during setup.

Option 1 is simpler for v1 (single-machine deployment).

---

## 19. Repo Structure

```
studyaio/
├── services/
│   ├── app/                          # FastAPI + Celery (modular monolith)
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py              # FastAPI app factory
│   │   │   ├── config.py            # Settings from env vars
│   │   │   ├── worker.py            # Celery app factory
│   │   │   ├── api/                 # FastAPI routers
│   │   │   │   ├── uploads.py
│   │   │   │   ├── courses.py
│   │   │   │   ├── summaries.py
│   │   │   │   ├── qa.py
│   │   │   │   ├── review.py
│   │   │   │   ├── flashcards.py
│   │   │   │   └── quizzes.py
│   │   │   ├── models/              # SQLAlchemy ORM
│   │   │   │   ├── course.py
│   │   │   │   ├── artifact.py
│   │   │   │   ├── extraction.py
│   │   │   │   ├── summary.py
│   │   │   │   ├── chunk.py
│   │   │   │   ├── flashcard.py
│   │   │   │   ├── quiz.py
│   │   │   │   ├── review_item.py
│   │   │   │   └── pipeline_run.py
│   │   │   ├── pipeline/            # Pipeline stage tasks
│   │   │   │   ├── orchestrator.py  # Celery chain builder
│   │   │   │   ├── ingest.py
│   │   │   │   ├── classify.py
│   │   │   │   ├── extract.py
│   │   │   │   ├── summarize.py
│   │   │   │   ├── index.py
│   │   │   │   └── assets.py
│   │   │   ├── agents/              # Agent adapter system
│   │   │   │   ├── base.py          # Abstract AgentAdapter
│   │   │   │   ├── claude_code.py   # v1 implementation
│   │   │   │   └── factory.py       # Returns configured adapter
│   │   │   ├── extractors/          # File parsers
│   │   │   │   ├── pdf.py
│   │   │   │   ├── docx.py
│   │   │   │   └── pptx.py
│   │   │   ├── services/            # Business logic layer
│   │   │   │   ├── course_service.py
│   │   │   │   ├── search_service.py
│   │   │   │   └── review_service.py
│   │   │   └── core/                # Shared utilities
│   │   │       ├── database.py
│   │   │       ├── redis.py
│   │   │       └── utils.py
│   │   ├── prompts/                 # AI prompt templates
│   │   │   ├── classify.txt
│   │   │   ├── summarize.txt
│   │   │   ├── summarize_update.txt
│   │   │   ├── flashcards.txt
│   │   │   ├── quiz.txt
│   │   │   └── answer_question.txt
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   ├── integration/
│   │   │   └── fixtures/
│   │   ├── alembic/                 # DB migrations
│   │   │   └── versions/
│   │   ├── alembic.ini
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── ui/                          # React frontend
│       ├── src/
│       │   ├── components/
│       │   ├── pages/
│       │   ├── hooks/
│       │   ├── api/                 # API client functions
│       │   └── App.jsx
│       ├── public/
│       ├── Dockerfile
│       ├── package.json
│       └── vite.config.js
│
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   ├── docker-compose.prod.yml
│   └── db/
│       └── init.sql                 # pgvector extension + initial schema
│
├── data/                            # Docker volumes (gitignored)
│   ├── uploads/
│   ├── extractions/
│   └── summaries/
│
├── scripts/
│   ├── import_v0.py                 # Import from existing repo structure
│   ├── seed_fixtures.py             # Load test data
│   └── reset_db.py                  # Dev utility
│
├── tests/
│   ├── fixtures/                    # Sample PDFs/PPTX/DOCX for testing
│   └── golden/                      # Expected outputs for golden tests
│
├── docs/
│   ├── PRD.md                       # This document
│   ├── architecture.md
│   ├── api.md                       # API endpoint documentation
│   ├── user_guide.md
│   └── developer_guide.md
│
├── new_lectures/                    # v0 compatibility: drop zone
├── raw_lectures/                    # v0 compatibility: organized files
├── lectures_summary/                # v0 compatibility: generated summaries
├── CLAUDE.md                        # v0 compatibility: Claude Code instructions
│
├── .env.example
├── .gitignore
├── README.md
└── Makefile                         # Common commands (make up, make test, etc.)
```

---

## 20. Testing Strategy

### Unit Tests

**What:** Individual functions and classes in isolation.

**Coverage targets:**
- File extractors (PDF, DOCX, PPTX parsing)
- Classification heuristics (filename parsing, confidence scoring)
- Chunking logic (stable ID generation, overlap handling)
- Idempotency logic (dedup checks, version incrementing)
- Review Item creation conditions
- API request/response schemas

**Tools:** pytest, pytest-asyncio

### Integration Tests

**What:** Pipeline stages working together with real (test) database and Redis.

**Coverage targets:**
- Full pipeline run on fixture files (upload → processed)
- Review Item creation and resolution flow
- Q&A retrieval and citation generation
- Idempotent re-upload behavior
- API endpoints with database

**Tools:** pytest, testcontainers (Postgres + Redis in Docker for tests), httpx (async API testing)

### Golden Tests

**What:** Expected outputs compared against known-good baselines.

**Coverage targets:**
- Given a specific test PDF → expected extraction manifest structure
- Given a specific extraction → expected summary structure (sections present, not exact content)
- Given a specific summary → expected flashcard/quiz structure

**Note:** Golden tests verify structure and key fields, not exact AI-generated text (which varies).

### Fixture Set

A set of sanitized test files in `tests/fixtures/`:
- 2-3 small PDFs (2-5 pages each) with known content
- 1 PPTX file with slides and images
- 1 DOCX file
- Files are either synthetic or sanitized versions of real lectures with permission

### Test Commands

```bash
make test              # Run all tests
make test-unit         # Unit tests only
make test-integration  # Integration tests (requires Docker)
make test-golden       # Golden/snapshot tests
```

---

## 21. Milestones & Delivery Plan

### Milestone 1 — Foundation & Pipeline (No UI)

**Goal:** Upload a file, pipeline runs, summary appears on disk and in database.

**Tasks:**
1. Set up repo structure, Docker Compose, database schema with Alembic migrations
2. Implement file extractors (PDF, DOCX, PPTX) as Python functions
3. Implement ingest stage (file hashing, dedup, storage)
4. Implement classify stage (Claude Code CLI integration, confidence scoring, Review Item creation)
5. Implement extract stage (full extraction with image extraction)
6. Implement summarize stage (Claude Code prompt, markdown generation with embedded images, idempotent updates)
7. Implement Celery pipeline orchestrator (chain stages, handle failures)
8. Write unit tests for extractors, classification heuristics, idempotency
9. Create fixture set and golden tests
10. Build `import_v0.py` script to migrate from existing repo structure

**Deliverable:** `make ingest path/to/file.pdf` triggers the full pipeline via CLI. Summary appears in database and on disk. Review Items viewable via `make review-list`.

### Milestone 2 — Web UI MVP

**Goal:** Upload files, browse courses/weeks, read summaries, resolve Review Items — all in the browser.

**Tasks:**
1. FastAPI endpoints: upload, list courses, list weeks, get summary, list/resolve Review Items
2. React project setup (Vite, Tailwind, React Router, React Query)
3. Dashboard page (courses overview, recent activity, review inbox count)
4. Upload page (drag-and-drop, progress indicator, SSE pipeline updates)
5. Course page (weeks list with status indicators)
6. Week view (summary rendered as markdown with embedded images, original file viewer)
7. Review Inbox page (list, resolve, dismiss)
8. Navigation (sidebar desktop, bottom tabs mobile concept)
9. API documentation

**Deliverable:** Functional web app where you can upload a PDF and browse the resulting summary.

### Milestone 3 — Search & Q&A

**Goal:** Ask questions and get answers with citations pointing to source pages/slides.

**Tasks:**
1. Implement indexing stage (chunking, stable IDs, embeddings via Claude Code or local model)
2. pgvector similarity search with scope filtering
3. Q&A endpoint (embed question → retrieve chunks → Claude Code answers with citations)
4. Q&A UI (question input, scope selector, answer with clickable citations)
5. "Jump to source" — clicking a citation opens the file viewer at the cited page
6. Integration tests for retrieval accuracy

**Deliverable:** Ask "What is a binary search tree?" scoped to CSIT302 and get an answer citing specific slides.

### Milestone 4 — Study Assets

**Goal:** Auto-generated flashcards and quizzes available per week.

**Tasks:**
1. Implement flashcard generation (Claude Code prompt, storage, idempotent regeneration)
2. Implement quiz generation (MCQ + short answer, storage, regeneration)
3. Flashcard UI (deck flip, navigate, shuffle)
4. Quiz UI (question presentation, answer submission, scoring, explanation reveal)
5. Add flashcard and quiz tabs to Week View
6. Pipeline integration — assets generated after summarization

**Deliverable:** Every processed week has flashcards and quizzes accessible in the UI.

### Milestone 5 — Polish & Portfolio

**Goal:** Production-grade quality suitable for daily use and portfolio showcase.

**Tasks:**
1. Error handling and recovery across the pipeline
2. Loading states, empty states, error states in UI
3. Mobile responsiveness pass
4. Performance optimization (query optimization, caching, lazy loading)
5. Documentation: README, architecture doc, user guide, developer guide
6. CI pipeline (lint, test, build)
7. Demo recording / screenshots for portfolio

**Deliverable:** A polished, documented, tested application ready for daily use and showcase.

---

## 22. Definition of Done (v1)

v1 is considered complete when all of the following are true:

- [ ] Upload a lecture file (PDF, DOCX, or PPTX) via the web UI
- [ ] Pipeline runs automatically without manual intervention
- [ ] Course and week are correctly classified (or a Review Item is created)
- [ ] Extraction produces per-page text and images
- [ ] A week summary is generated with all required sections and embedded images
- [ ] Re-uploading the same file does not create duplicates
- [ ] Uploading a new file for the same course+week updates the existing summary
- [ ] Chunks are indexed with embeddings for Q&A retrieval
- [ ] Q&A returns answers with accurate citations to source pages/slides
- [ ] Flashcards and quizzes are generated for each processed week
- [ ] Review Inbox shows pending items and allows resolution
- [ ] Resolving a Review Item triggers pipeline continuation
- [ ] All screens are functional: Dashboard, Course, Week View, Q&A, Review Inbox, Upload
- [ ] Existing Claude Code slash commands still work
- [ ] `docker compose up` starts the entire stack
- [ ] Unit and integration tests pass
- [ ] Core documentation exists (README, architecture, user guide)

---

## 23. Risks & Mitigations

### Claude Code CLI as a Background Service

**Risk:** Claude Code is designed for interactive use. Shelling out from a Celery worker may be brittle — authentication issues, unexpected prompts, rate limiting under Max plan.

**Mitigation:** Build robust error handling around the subprocess call. Implement retry with exponential backoff. Test thoroughly. Design the agent adapter interface so switching to direct API is a single-adapter swap (v1.5 escape hatch).

### Max Plan Rate Limits

**Risk:** Heavy pipeline runs (many files at once) may hit the Max plan's 5-hour rolling session limits shared between Claude Code CLI and web/app usage.

**Mitigation:** Queue jobs and process sequentially rather than in parallel during heavy loads. Add rate limit awareness to the worker (back off when limits are hit). Prioritize interactive Claude Code usage over background pipeline. Long-term: switch to API adapter with per-token billing.

### AI Output Quality Variance

**Risk:** Summaries, flashcards, and quizzes may vary in quality across runs, making idempotency imperfect at the content level.

**Mitigation:** Highly structured prompts with explicit format requirements. Golden tests that verify structure rather than exact content. Version tracking so you can see when content changed and why.

### Scope Creep

**Risk:** The deferred features (Exam Mode, CourseOps, Ollama) are tempting to start early, fragmenting effort across the core pipeline.

**Mitigation:** Strict milestone gating. Each milestone must be complete and tested before starting the next. The backlog exists to capture ideas, not to authorize work.

### Image Extraction Quality

**Risk:** Image extraction from PDFs and PPTX files can be lossy or miss embedded diagrams.

**Mitigation:** Use proven libraries (pymupdf/fitz for PDF, python-pptx for PPTX). Test with real lecture files. For complex diagrams, fall back to screenshots/page renders if extraction fails.

---

## 24. Backlog (Future Ideas)

These are captured for future consideration. None are committed.

**Study UX**
- Spaced repetition for flashcards (SM-2 algorithm)
- "I have 45 minutes" session generator
- Streaks and weekly goals
- Weak topic detection from quiz performance

**Automation & Quality**
- Lecture diff when a file is re-uploaded (show what changed)
- Confidence scores displayed on all derived content
- Duplicate detection and merge suggestions
- Batch import from a folder (drag entire semester)

**Integrations**
- Obsidian export (markdown vault structure)
- GitHub Issues export for deadlines
- Canvas iCal merge
- Notion export

**Infrastructure**
- MinIO for object storage (clean separation from app containers)
- Nginx reverse proxy with HTTPS
- Prometheus + Grafana monitoring
- Backup strategy for Postgres

**Mobile**
- PWA with offline caching for summaries and flashcards
- Push notifications for Review Items
- Share sheet integration (upload from phone camera/files)

---

*End of PRD*
