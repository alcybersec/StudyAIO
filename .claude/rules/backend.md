# Rules for services/app/

## API Routes (app/api/)
- Routes are thin controllers: validate → call service → return response
- Always use Pydantic models for request/response schemas
- Define schemas next to the router file or in a schemas/ subdir
- Use dependency injection for database sessions: `Depends(get_db)`
- Return proper HTTP status codes (201 for creation, 404 for not found, etc.)
- Use `HTTPException` for error responses with meaningful detail messages
- Group endpoints by resource with APIRouter and prefix

## Models (app/models/)
- One model per file
- Use `mapped_column` (SQLAlchemy 2.0 style)
- UUIDs as primary keys (uuid7 for time-sortable)
- Include `created_at` and `updated_at` on all tables
- Add `__tablename__` explicitly
- Add relevant indexes in the model definition
- Keep models as data containers — no business logic in models

## Pipeline (app/pipeline/)
- Each stage is a Celery task decorated with `@celery_app.task`
- Tasks receive primitive arguments (artifact_id as string, not ORM objects)
- Tasks create their own database session
- Tasks must be idempotent — safe to retry
- On failure: log the error, update PipelineRun, raise for Celery retry
- On low confidence: create ReviewItem, set artifact to waiting_review
- On success: update PipelineRun, enqueue next stage

## Agents (app/agents/)
- All AI operations go through the AgentAdapter interface
- Never import or call Claude Code directly outside of claude_code.py
- Return structured dataclasses/Pydantic models, never raw strings
- Include error handling for CLI failures (timeout, auth issues, rate limits)
- Log all AI calls with input/output token counts if available

## Services (app/services/)
- Business logic lives here
- Services receive database sessions as parameters
- Services are stateless — no instance variables
- Services handle idempotency checks (dedup, versioning)
- Services raise domain-specific exceptions (not HTTP exceptions)

## Extractors (app/extractors/)
- One extractor per file type (pdf.py, docx.py, pptx.py)
- All extractors return the same structured format (ExtractionResult dataclass)
- Extractors write images to disk and reference them in the manifest
- Extractors must not modify the original file
- Handle corrupted/malformed files gracefully with clear error messages
