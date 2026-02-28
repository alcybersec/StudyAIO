# Review Code

Review the recent changes or specified files for quality issues.

## Checklist

### Architecture Compliance
- [ ] Database is source of truth (not filesystem)
- [ ] AI calls go through AgentAdapter, not called directly
- [ ] Pipeline stages are separate Celery tasks
- [ ] Business logic is in services/, not in routes or tasks
- [ ] API routes are thin (validate → service → response)

### Code Quality
- [ ] Type hints on all functions (params + return)
- [ ] Docstrings on all public functions/classes (Google style)
- [ ] No print() statements (use structlog)
- [ ] No hardcoded paths (use config.py)
- [ ] No wildcard imports
- [ ] Custom exceptions used, not generic Exception
- [ ] No bare except clauses

### Idempotency
- [ ] File uploads checked against SHA-256 hash before creating records
- [ ] Summaries use (course_id, week) unique constraint — update, don't duplicate
- [ ] Chunks use stable_id for upsert
- [ ] Flashcards/quizzes replaced on regeneration via generation_version

### Testing
- [ ] New code has corresponding tests
- [ ] Tests are in the correct directory (mirrors source structure)
- [ ] Unit tests don't depend on external services
- [ ] Test names clearly describe what's being tested

### Security & Safety
- [ ] No secrets in code or config files
- [ ] User file uploads are validated (type, size)
- [ ] File paths are sanitized (no path traversal)
- [ ] SQL uses parameterized queries (via SQLAlchemy ORM)

## Output

For each issue found, report:
1. **File and line**
2. **Issue** — what's wrong
3. **Fix** — specific recommendation
4. **Severity** — (critical / warning / suggestion)
