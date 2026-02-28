---
name: pipeline-stage
description: Build or modify a pipeline stage for StudyAIO. Use when creating new Celery tasks for the ingest/classify/extract/summarize/index/assets pipeline stages, or when debugging pipeline issues.
---

# Pipeline Stage Development

## Structure of a Pipeline Stage

Every pipeline stage follows this pattern:

```python
# app/pipeline/<stage_name>.py

from celery import shared_task
from sqlalchemy.orm import Session
from app.core.database import get_session
from app.models.pipeline_run import PipelineRun
from app.models.artifact import LectureArtifact
import structlog

logger = structlog.get_logger()

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def <stage_name>_task(self, artifact_id: str) -> dict:
    """<Description of what this stage does>.
    
    Args:
        artifact_id: UUID of the LectureArtifact to process.
        
    Returns:
        Dict with stage results for the next stage in the chain.
    """
    with get_session() as db:
        # 1. Load the artifact
        artifact = db.get(LectureArtifact, artifact_id)
        if not artifact:
            raise ValueError(f"Artifact {artifact_id} not found")
        
        # 2. Create/update pipeline run
        run = PipelineRun(
            artifact_id=artifact_id,
            stage="<stage_name>",
            status="running",
        )
        db.add(run)
        db.commit()
        
        try:
            # 3. Do the work (call services, extractors, agents)
            result = do_the_actual_work(db, artifact)
            
            # 4. Update pipeline run on success
            run.status = "completed"
            run.duration_ms = calculate_duration()
            db.commit()
            
            logger.info("pipeline_stage_completed",
                stage="<stage_name>",
                artifact_id=artifact_id,
            )
            
            return {"artifact_id": artifact_id, **result}
            
        except Exception as e:
            # 5. Update pipeline run on failure
            run.status = "failed"
            run.error_message = str(e)
            db.commit()
            
            logger.error("pipeline_stage_failed",
                stage="<stage_name>",
                artifact_id=artifact_id,
                error=str(e),
            )
            
            # 6. Retry via Celery
            raise self.retry(exc=e)
```

## Checklist for Every Stage

- [ ] Task receives `artifact_id` as string (not ORM object)
- [ ] Task creates its own database session
- [ ] PipelineRun record created at start, updated at end
- [ ] Structured logging with stage name and artifact_id
- [ ] Errors caught, logged, and retried via Celery
- [ ] Idempotent: running twice produces the same result
- [ ] Returns a dict with at least `artifact_id` for chain continuation
- [ ] Has unit tests with mocked dependencies
- [ ] Has integration test with real database

## Stage-Specific Guidance

### Ingest
- Compute SHA-256 first, check for existing artifact before saving file
- Save to `data/uploads/` with hash prefix in filename

### Classify
- Call AgentAdapter.classify_lecture()
- Check confidence against CLASSIFICATION_CONFIDENCE_THRESHOLD
- If low confidence: create ReviewItem, set artifact.status = "waiting_review", do NOT chain next stage

### Extract
- Select extractor based on artifact.file_type
- Save images to `data/extractions/<artifact_id>/images/`
- Create Extraction record with manifest JSON

### Summarize
- Check for existing Summary at (course_id, week)
- If exists: pass existing summary to agent for update
- If new: generate fresh summary
- Increment version on update
- Write markdown file to `data/summaries/<course_code>/`

### Index
- Generate stable chunk IDs: `<sha256_prefix>_p<page>_c<index>`
- Upsert chunks (don't duplicate on re-index)
- Generate embeddings via agent or embedding model

### Assets
- Generate flashcards and quiz questions via agent
- Replace existing assets for same course+week (bump generation_version)
