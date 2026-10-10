"""Pipeline SSE events publish to the artifact row's owner (R-022).

Since AI-012 the stages act as ``artifact.user_id``; the Celery payload's
``user_id`` is advisory. The task wrappers must publish to the same owner, so a
payload naming another user can never receive an event for a row it does not own.
"""

import contextlib
import importlib
from unittest.mock import patch

import pytest

ROW = "user-row-owner"
PAYLOAD = "user-payload-other"
ART = "art-001"

# (module, task attr, non-retry error class name in the module)
STAGES = [
    ("classify", "classify_artifact", "ClassificationError"),
    ("extract", "extract_artifact", "ExtractionError"),
    ("summarize", "summarize_artifact", "SummarizationError"),
    ("index", "index_artifact", "IndexingError"),
    ("assets", "generate_assets", "AssetGenerationError"),
]


def _effect_kwargs(effect):
    if isinstance(effect, BaseException):
        return {"side_effect": effect}
    return {"return_value": effect}


def _run(mod_name, task_name, effect, payload_user=PAYLOAD, row_owner=ROW):
    """Invoke a stage task with the row-owner lookup and the publisher mocked."""
    mod = importlib.import_module(f"app.pipeline.{mod_name}")
    task = getattr(mod, task_name)
    with (
        patch(f"app.pipeline.{mod_name}.publish_pipeline_event_sync") as pub,
        patch(f"app.pipeline.{mod_name}.run_async", **_effect_kwargs(effect)),
        patch("app.pipeline._owner._row_owner", return_value=row_owner),
    ):
        outcome = None
        try:
            outcome = task({"artifact_id": ART, "user_id": payload_user, "status": "ingested"})
        except BaseException as exc:  # noqa: BLE001 - the failure paths raise
            outcome = exc
    return pub, outcome


def _owners(pub):
    return [c.kwargs.get("user_id") for c in pub.call_args_list]


def _statuses(pub):
    return [c.args[2] for c in pub.call_args_list]


@pytest.mark.parametrize(("mod", "task", "err"), STAGES)
class TestStageEventsGoToRowOwner:
    def test_success_publishes_only_to_row_owner(self, mod, task, err):
        pub, _ = _run(mod, task, {"artifact_id": ART, "status": "completed"})
        assert len(pub.call_args_list) == 2  # started + terminal
        assert _owners(pub) == [ROW, ROW]
        assert PAYLOAD not in _owners(pub)

    def test_waiting_review_publishes_only_to_row_owner(self, mod, task, err):
        pub, _ = _run(mod, task, {"artifact_id": ART, "status": "waiting_review"})
        assert _statuses(pub) == ["started", "waiting_review"]
        assert _owners(pub) == [ROW, ROW]

    def test_non_retry_failure_publishes_only_to_row_owner(self, mod, task, err):
        exc_cls = getattr(importlib.import_module(f"app.pipeline.{mod}"), err)
        pub, outcome = _run(mod, task, exc_cls("boom"))
        assert isinstance(outcome, exc_cls)
        assert _statuses(pub) == ["started", "failed"]
        assert _owners(pub) == [ROW, ROW]

    def test_retry_failure_publishes_only_to_row_owner(self, mod, task, err):
        pub, outcome = _run(mod, task, RuntimeError("transient"))
        assert outcome is not None
        assert _statuses(pub) == ["started", "failed"]
        assert _owners(pub) == [ROW, ROW]

    def test_missing_row_publishes_nothing_to_payload_user(self, mod, task, err):
        exc_cls = getattr(importlib.import_module(f"app.pipeline.{mod}"), err)
        pub, _ = _run(mod, task, exc_cls("not found"), row_owner=None)
        assert PAYLOAD not in _owners(pub)
        assert all(o is None for o in _owners(pub))  # None => dropped by the publisher

    def test_matching_payload_still_publishes_to_owner(self, mod, task, err):
        pub, _ = _run(mod, task, {"artifact_id": ART, "status": "completed"}, payload_user=ROW)
        assert _owners(pub) == [ROW, ROW]


class TestIngestEventsGoToRowOwner:
    def _run(self, payload, effect, row_owner=ROW):
        from app.pipeline.ingest import ingest_file

        with (
            patch("app.pipeline.ingest.publish_pipeline_event_sync") as pub,
            patch("app.pipeline.ingest.run_async", **_effect_kwargs(effect)),
            patch("app.pipeline._owner._row_owner", return_value=row_owner),
        ):
            with contextlib.suppress(BaseException):  # failure paths raise
                ingest_file(payload)
        return pub

    def test_precreated_artifact_success_goes_to_row_owner(self):
        pub = self._run(
            {"file_path": "f.pdf", "user_id": PAYLOAD, "artifact_id": ART},
            {"artifact_id": ART, "status": "ingested"},
        )
        assert _owners(pub) == [ROW, ROW]

    def test_precreated_artifact_failure_goes_to_row_owner(self):
        pub = self._run(
            {"file_path": "f.pdf", "user_id": PAYLOAD, "artifact_id": ART},
            RuntimeError("x"),
        )
        assert _statuses(pub) == ["started", "failed"]
        assert _owners(pub) == [ROW, ROW]

    def test_duplicate_result_resolves_owner_of_existing_row(self):
        pub = self._run(
            {"file_path": "f.pdf", "user_id": PAYLOAD, "artifact_id": ART},
            {"artifact_id": "existing-1", "status": "duplicate"},
        )
        assert PAYLOAD not in _owners(pub)

    def test_unknown_row_publishes_nothing_to_payload_user(self):
        pub = self._run(
            {"file_path": "f.pdf", "user_id": PAYLOAD, "artifact_id": ART},
            RuntimeError("x"),
            row_owner=None,
        )
        assert PAYLOAD not in _owners(pub)

    def test_no_artifact_yet_uses_payload_user(self):
        """No row exists: ingest creates it owned by the payload user, so that is the owner."""
        pub = self._run({"file_path": "f.pdf", "user_id": PAYLOAD}, RuntimeError("x"))
        assert _owners(pub) == [PAYLOAD, PAYLOAD]
