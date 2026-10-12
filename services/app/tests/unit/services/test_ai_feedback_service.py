"""AI feedback service: validation, target ownership, upsert semantics (GL#36)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.ai_feedback import AI_FEEDBACK_REASONS, AI_FEEDBACK_TARGET_TYPES, AIFeedback
from app.services import ai_feedback_service as svc

USER = "user-1"


def _result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _target(course_id="course-1"):
    target = MagicMock()
    target.course_id = course_id
    return target


class TestValidation:
    @pytest.mark.parametrize("bad", ["", "summary ", "quiz", "SUMMARY", "course"])
    async def test_unknown_target_type_rejected(self, mock_session, bad):
        with pytest.raises(ValueError, match="target_type"):
            await svc.upsert_vote(
                mock_session, user_id=USER, target_type=bad, target_id="t-1", rating=1
            )
        mock_session.add.assert_not_called()

    @pytest.mark.parametrize("bad", [0, 2, -2, 5, True])
    async def test_rating_must_be_plus_or_minus_one(self, mock_session, bad):
        with pytest.raises(ValueError, match="rating"):
            await svc.upsert_vote(
                mock_session, user_id=USER, target_type="summary", target_id="t-1", rating=bad
            )

    async def test_unknown_reason_rejected(self, mock_session):
        with pytest.raises(ValueError, match="reason"):
            await svc.upsert_vote(
                mock_session,
                user_id=USER,
                target_type="summary",
                target_id="t-1",
                rating=-1,
                reason="boring",
            )

    async def test_reason_not_allowed_on_thumbs_up(self, mock_session):
        with pytest.raises(ValueError, match="reason"):
            await svc.upsert_vote(
                mock_session,
                user_id=USER,
                target_type="summary",
                target_id="t-1",
                rating=1,
                reason="inaccurate",
            )

    async def test_comment_over_limit_rejected_at_limit_accepted(self, mock_session):
        with pytest.raises(ValueError, match="comment"):
            await svc.upsert_vote(
                mock_session,
                user_id=USER,
                target_type="summary",
                target_id="t-1",
                rating=-1,
                comment="x" * 1001,
            )
        with patch.object(
            svc.summary_service, "get_summary_by_id", AsyncMock(return_value=_target())
        ):
            mock_session.execute.return_value = _result(None)
            vote = await svc.upsert_vote(
                mock_session,
                user_id=USER,
                target_type="summary",
                target_id="t-1",
                rating=-1,
                comment="x" * 1000,
            )
        assert len(vote.comment) == 1000

    def test_constants_match_model(self):
        assert set(svc.TARGET_TYPES) == set(AI_FEEDBACK_TARGET_TYPES)
        assert set(svc.REASONS) == set(AI_FEEDBACK_REASONS)


class TestTargetOwnership:
    """Floor 1: the target lookup carries the caller; not-owned == not-found."""

    @pytest.mark.parametrize(
        ("target_type", "module", "name"),
        [
            ("summary", "summary_service", "get_summary_by_id"),
            ("flashcard", "srs_service", "get_owned_flashcard"),
            ("quiz_question", "exam_service", "get_owned_quiz_question"),
        ],
    )
    async def test_getter_receives_the_caller(self, mock_session, target_type, module, name):
        getter = AsyncMock(return_value=None)
        with patch.object(getattr(svc, module), name, getter):
            with pytest.raises(svc.FeedbackTargetNotFoundError):
                await svc.upsert_vote(
                    mock_session,
                    user_id=USER,
                    target_type=target_type,
                    target_id="foreign-id",
                    rating=1,
                )
        assert getter.await_args.kwargs.get("user_id") == USER  # load-bearing
        assert getter.await_args.args[1] == "foreign-id"
        mock_session.add.assert_not_called()

    @pytest.mark.parametrize("target_type", ["answer", "chat_message"])
    async def test_chat_targets_scoped_to_caller(self, mock_session, target_type):
        mock_session.execute.return_value = _result(None)
        with pytest.raises(svc.FeedbackTargetNotFoundError):
            await svc.upsert_vote(
                mock_session,
                user_id=USER,
                target_type=target_type,
                target_id="m-1",
                rating=1,
            )
        compiled = mock_session.execute.await_args.args[0].compile()
        assert "chat_sessions.user_id" in str(compiled)
        assert USER in compiled.params.values()

    async def test_answer_requires_assistant_role(self, mock_session):
        mock_session.execute.return_value = _result(None)
        with pytest.raises(svc.FeedbackTargetNotFoundError):
            await svc.upsert_vote(
                mock_session, user_id=USER, target_type="answer", target_id="m-1", rating=1
            )
        assert "assistant" in mock_session.execute.await_args.args[0].compile().params.values()


class TestUpsert:
    async def test_new_vote_inserted_with_inferred_course(self, mock_session):
        with patch.object(
            svc.srs_service, "get_owned_flashcard", AsyncMock(return_value=_target("course-9"))
        ):
            mock_session.execute.return_value = _result(None)
            vote = await svc.upsert_vote(
                mock_session,
                user_id=USER,
                target_type="flashcard",
                target_id="card-1",
                rating=-1,
                reason="inaccurate",
                comment="wrong date",
            )
        mock_session.add.assert_called_once_with(vote)
        assert isinstance(vote, AIFeedback)
        assert (vote.user_id, vote.target_type, vote.target_id) == (USER, "flashcard", "card-1")
        assert (vote.rating, vote.reason, vote.comment) == (-1, "inaccurate", "wrong date")
        assert vote.course_id == "course-9"

    async def test_second_vote_replaces_the_first(self, mock_session):
        existing = AIFeedback(
            user_id=USER,
            target_type="summary",
            target_id="s-1",
            rating=-1,
            reason="unclear",
            comment="meh",
            course_id="course-1",
        )
        with patch.object(
            svc.summary_service, "get_summary_by_id", AsyncMock(return_value=_target("course-1"))
        ):
            mock_session.execute.return_value = _result(existing)
            vote = await svc.upsert_vote(
                mock_session, user_id=USER, target_type="summary", target_id="s-1", rating=1
            )
        assert vote is existing
        mock_session.add.assert_not_called()
        assert (existing.rating, existing.reason, existing.comment) == (1, None, None)

    async def test_existing_vote_lookup_filters_on_user(self, mock_session):
        with patch.object(
            svc.summary_service, "get_summary_by_id", AsyncMock(return_value=_target())
        ):
            mock_session.execute.return_value = _result(None)
            await svc.upsert_vote(
                mock_session, user_id=USER, target_type="summary", target_id="s-1", rating=1
            )
        stmt = mock_session.execute.await_args.args[0]
        assert "ai_feedback.user_id" in str(stmt.compile())
        assert USER in stmt.compile().params.values()


class TestDeleteAndList:
    async def test_delete_is_scoped_to_caller(self, mock_session):
        mock_session.execute.return_value = MagicMock(rowcount=1)
        assert await svc.delete_vote(
            mock_session, user_id=USER, target_type="summary", target_id="s-1"
        )
        stmt = mock_session.execute.await_args.args[0]
        assert "ai_feedback.user_id" in str(stmt.compile())
        assert USER in stmt.compile().params.values()

    async def test_delete_nothing_returns_false(self, mock_session):
        mock_session.execute.return_value = MagicMock(rowcount=0)
        assert not await svc.delete_vote(
            mock_session, user_id=USER, target_type="summary", target_id="s-1"
        )

    async def test_list_is_scoped_and_validates_type(self, mock_session):
        with pytest.raises(ValueError, match="target_type"):
            await svc.list_votes(mock_session, user_id=USER, target_type="nope", target_ids=["a"])
        await svc.list_votes(mock_session, user_id=USER, target_type="summary", target_ids=["a"])
        stmt = mock_session.execute.await_args.args[0]
        assert "ai_feedback.user_id" in str(stmt.compile())
        assert USER in stmt.compile().params.values()

    async def test_list_empty_ids_skips_query(self, mock_session):
        result = await svc.list_votes(
            mock_session, user_id=USER, target_type="summary", target_ids=[]
        )
        assert result == []
        mock_session.execute.assert_not_called()


class TestAdminSummary:
    def test_shape_assembled_from_rows(self):
        out = svc.build_admin_summary(
            by_target=[("summary", 1, 3), ("summary", -1, 1), ("flashcard", -1, 2)],
            by_reason=[("inaccurate", 2), ("unclear", 1)],
            recent=[
                {
                    "target_type": "flashcard",
                    "reason": "inaccurate",
                    "comment": "bad",
                    "course_id": "c-1",
                    "created_at": "2026-10-10T00:00:00+00:00",
                }
            ],
        )
        assert out["total"] == 6
        assert out["by_rating"] == {"up": 3, "down": 3}
        assert out["by_target_type"]["summary"] == {"up": 3, "down": 1}
        assert out["by_target_type"]["flashcard"] == {"up": 0, "down": 2}
        assert out["by_reason"] == {"inaccurate": 2, "unclear": 1}
        assert "user_id" not in out["recent_negative"][0]
