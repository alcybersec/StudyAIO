# Rules for tests/

## Test Organization
- `tests/unit/` — fast, no external dependencies, everything mocked
- `tests/integration/` — uses real database and Redis (via testcontainers or Docker)
- `tests/fixtures/` — sample files (small PDFs, PPTX, DOCX) for pipeline testing
- `tests/golden/` — expected output structures for snapshot testing

## Naming
- Test files: `test_<module>.py` mirroring source structure
- Test functions: `test_<action>_<condition>_<expected>` e.g., `test_ingest_duplicate_file_returns_existing_artifact`
- Test classes: `class Test<Feature>:` to group related tests

## Fixtures
- Define reusable fixtures in `conftest.py` at the appropriate level
- Common fixtures: `db_session`, `test_client`, `sample_pdf`, `sample_course`, `sample_artifact`
- Use factory fixtures for entities that need variations: `make_artifact(course="CSIT302", week=3)`
- Always clean up: use function-scoped sessions that rollback after each test

## What to Test

### Unit tests MUST cover:
- All extractor functions (each file type)
- Classification heuristics (confidence scoring, pattern matching)
- Chunking logic (stable ID generation, overlap)
- Idempotency logic (dedup, version checks)
- Pydantic schema validation
- Service layer business logic

### Integration tests MUST cover:
- Full pipeline run on a fixture file (upload → processed status)
- Review Item creation and resolution
- API endpoints (upload, list, get, resolve)
- Database constraint enforcement (unique constraints, foreign keys)

### Golden tests MUST cover:
- Extraction manifest structure (correct fields, types)
- Summary markdown structure (all required sections present)
- Flashcard/quiz output structure

## What NOT to Test
- Exact AI-generated text (it varies between runs)
- Third-party library internals
- Docker Compose orchestration (test services individually)
- UI visual appearance (that's manual review)

## Test Data
- Fixture files in `tests/fixtures/` must be small (< 500KB each)
- Never use real student data — create synthetic test files
- Fixtures are committed to git (they're part of the test suite)
- Golden test expectations are committed to git
