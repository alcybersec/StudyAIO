"""Floor 1 (C6): pipeline owner scoping — the artifact row's owner wins."""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import ClassificationResult

ROW_OWNER = "user-row-owner"
PAYLOAD_OWNER = "user-someone-else"


class TestGetOrCreateCourseRequiresOwner:
    def test_user_id_has_no_default(self):
        from app.pipeline.classify import _get_or_create_course

        param = inspect.signature(_get_or_create_course).parameters["user_id"]
        assert param.default is inspect.Parameter.empty

    async def test_lookup_is_filtered_on_user_id(self):
        from app.pipeline.classify import _get_or_create_course

        session = AsyncMock()
        res = MagicMock()
        res.scalar_one_or_none.return_value = MagicMock()
        session.execute.return_value = res
        await _get_or_create_course(session, "CSIT302", ROW_OWNER)
        stmt = session.execute.await_args.args[0]
        assert ROW_OWNER in stmt.compile().params.values()

    async def test_empty_owner_is_rejected(self):
        from app.pipeline.classify import _get_or_create_course

        session = AsyncMock()
        with pytest.raises(ValueError):
            await _get_or_create_course(session, "CSIT302", "")
        session.execute.assert_not_called()


class TestRowOwnerWins:
    @patch("app.pipeline.classify.get_agent")
    @patch("app.pipeline.classify._extract_text_preview", return_value="text")
    @patch("app.pipeline.classify._get_or_create_course", new_callable=AsyncMock)
    @patch("app.pipeline.classify._get_known_courses", new_callable=AsyncMock)
    @patch("app.pipeline.classify.record_agent_usage", create=True)
    @patch("app.pipeline.classify.async_session_factory")
    async def test_classify_ignores_mismatched_payload_owner(
        self, factory, _usage, known, get_course, _preview, get_agent
    ):
        from app.pipeline.classify import _classify

        artifact = MagicMock()
        artifact.id = "art-001"
        artifact.user_id = ROW_OWNER
        artifact.file_path = "/x.pdf"
        artifact.file_type = "pdf"
        artifact.original_filename = "a.pdf"
        session = AsyncMock()
        session.add = MagicMock()
        res = MagicMock()
        res.scalar_one_or_none.return_value = artifact
        session.execute.return_value = res
        factory.return_value.__aenter__ = AsyncMock(return_value=session)
        factory.return_value.__aexit__ = AsyncMock(return_value=False)
        known.return_value = []
        get_course.return_value = MagicMock(id="c1")
        agent = AsyncMock()
        agent.classify_lecture.return_value = ClassificationResult(
            course_code="CSIT302", week=5, title="t", confidence=0.99, reasoning="r"
        )
        get_agent.return_value = agent

        with (
            patch("app.services.settings_service.get_user_agent_config", new_callable=AsyncMock) as cfg,
            patch("app.services.billing_service.record_agent_usage", new_callable=AsyncMock) as usage,
        ):
            result = await _classify("art-001", user_id=PAYLOAD_OWNER)

        assert result["user_id"] == ROW_OWNER
        assert known.await_args.args[1] == ROW_OWNER
        assert cfg.await_args.args[1] == ROW_OWNER
        assert usage.await_args.args[1] == ROW_OWNER
        assert get_course.await_args.kwargs["user_id"] == ROW_OWNER


class TestOwnerMismatchHelper:
    def test_mismatch_logs_warning(self):
        from app.pipeline import _owner

        with patch.object(_owner, "logger") as log:
            _owner.warn_on_owner_mismatch("classify", "art-1", ROW_OWNER, PAYLOAD_OWNER)
        log.warning.assert_called_once()

    def test_match_or_absent_payload_is_silent(self):
        from app.pipeline import _owner

        with patch.object(_owner, "logger") as log:
            _owner.warn_on_owner_mismatch("classify", "art-1", ROW_OWNER, ROW_OWNER)
            _owner.warn_on_owner_mismatch("classify", "art-1", ROW_OWNER, None)
        log.warning.assert_not_called()
