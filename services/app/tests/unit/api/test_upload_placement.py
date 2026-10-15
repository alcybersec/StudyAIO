"""Explicit course/week on upload skips classification (GL#49, audit PROD-07)."""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import QuotaExceededError

PDF = b"%PDF-1.4 body"


@pytest.fixture
def placed():
    """Patch the collaborators of the upload path; yield the mocks."""
    artifact = MagicMock(id="art-1", file_path="uploads/art-1_x.pdf")
    course = MagicMock(id="course-1", code="CSIT302")
    with (
        patch(
            "app.api.uploads.artifact_service.check_duplicate",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.api.uploads.artifact_service.create_upload_artifact",
            new_callable=AsyncMock,
            return_value=artifact,
        ) as create,
        patch(
            "app.api.uploads.course_service.get_or_create_course",
            new_callable=AsyncMock,
            return_value=course,
        ) as get_course,
        patch("app.api.uploads.run_pipeline", return_value=MagicMock(id="t-full")) as full,
        patch("app.api.uploads.resume_pipeline", return_value=MagicMock(id="t-resume")) as resume,
    ):
        yield MagicMock(create=create, get_course=get_course, full=full, resume=resume)


@pytest.mark.asyncio
class TestSingleUploadPlacement:
    async def test_course_and_week_skip_classify(self, async_client, default_test_user, placed):
        r = await async_client.post(
            "/api/uploads",
            files={"file": ("a.pdf", PDF, "application/pdf")},
            data={"course_code": "CSIT302", "week": "4"},
        )
        assert r.status_code == 201
        assert r.json()["status"] == "processing"
        assert placed.get_course.await_args.args[1] == "CSIT302"
        assert placed.get_course.await_args.kwargs.get("user_id") == default_test_user.id
        assert placed.get_course.await_args.kwargs.get("tier") == default_test_user.tier
        kw = placed.create.await_args.kwargs
        assert kw["course_id"] == "course-1"
        assert kw["week"] == 4
        placed.resume.assert_called_once()
        assert placed.resume.call_args.args[:2] == ("art-1", "extract")
        assert placed.resume.call_args.kwargs["user_id"] == default_test_user.id
        placed.full.assert_not_called()

    async def test_absent_keeps_ai_routing(self, async_client, placed):
        r = await async_client.post("/api/uploads", files={"file": ("a.pdf", PDF, "x/y")})
        assert r.status_code == 201
        placed.full.assert_called_once()
        placed.resume.assert_not_called()
        placed.get_course.assert_not_awaited()
        assert "course_id" not in placed.create.await_args.kwargs

    async def test_blank_form_values_mean_absent(self, async_client, placed):
        r = await async_client.post(
            "/api/uploads",
            files={"file": ("a.pdf", PDF, "x/y")},
            data={"course_code": "", "week": ""},
        )
        assert r.status_code == 201
        placed.full.assert_called_once()

    @pytest.mark.parametrize(
        "data",
        [
            {"course_code": "CSIT302"},
            {"week": "3"},
            {"course_code": "CSIT302", "week": "0"},
            {"course_code": "CSIT302", "week": "53"},
            {"course_code": "X" * 21, "week": "3"},
        ],
    )
    async def test_invalid_placement_is_422_and_stores_nothing(self, async_client, placed, data):
        r = await async_client.post(
            "/api/uploads", files={"file": ("a.pdf", PDF, "x/y")}, data=data
        )
        assert r.status_code == 422
        placed.create.assert_not_awaited()

    async def test_course_quota_refuses_before_storing(self, async_client, placed):
        placed.get_course.side_effect = QuotaExceededError("courses", 3, "account")
        r = await async_client.post(
            "/api/uploads",
            files={"file": ("a.pdf", PDF, "x/y")},
            data={"course_code": "NEW1", "week": "1"},
        )
        assert r.status_code in (402, 403)
        placed.create.assert_not_awaited()

    async def test_duplicate_ignores_placement(self, async_client, placed):
        existing = MagicMock(id="old")
        with patch(
            "app.api.uploads.artifact_service.check_duplicate",
            new_callable=AsyncMock,
            return_value=existing,
        ):
            r = await async_client.post(
                "/api/uploads",
                files={"file": ("a.pdf", PDF, "x/y")},
                data={"course_code": "CSIT302", "week": "2"},
            )
        assert r.json()["status"] == "duplicate"
        assert r.json()["artifact_id"] == "old"
        placed.create.assert_not_awaited()
        placed.resume.assert_not_called()


@pytest.mark.asyncio
class TestBatchUploadPlacement:
    async def test_placement_applies_to_every_file(self, async_client, default_test_user, placed):
        files = [
            ("files", ("a.pdf", io.BytesIO(PDF + b"1"), "x/y")),
            ("files", ("b.pdf", io.BytesIO(PDF + b"2"), "x/y")),
        ]
        r = await async_client.post(
            "/api/uploads/batch", files=files, data={"course_code": "CSIT302", "week": "2"}
        )
        assert r.status_code == 201
        assert r.json()["succeeded"] == 2
        assert placed.get_course.await_count == 1  # resolved once, not per file
        assert placed.get_course.await_args.kwargs.get("user_id") == default_test_user.id
        assert placed.get_course.await_args.kwargs.get("tier") == default_test_user.tier
        assert placed.resume.call_count == 2
        placed.full.assert_not_called()
        for call in placed.create.await_args_list:
            assert call.kwargs["course_id"] == "course-1"
            assert call.kwargs["week"] == 2

    async def test_absent_is_unchanged(self, async_client, placed):
        files = [("files", ("a.pdf", io.BytesIO(PDF), "x/y"))]
        r = await async_client.post("/api/uploads/batch", files=files)
        assert r.status_code == 201
        placed.full.assert_called_once()
        placed.resume.assert_not_called()

    async def test_half_given_is_422(self, async_client, placed):
        files = [("files", ("a.pdf", io.BytesIO(PDF), "x/y"))]
        r = await async_client.post("/api/uploads/batch", files=files, data={"week": "2"})
        assert r.status_code == 422
        placed.create.assert_not_awaited()


@pytest.mark.asyncio
class TestGetOrCreateCourse:
    async def test_existing_course_matched_case_insensitively_and_scoped(self, mock_session):
        from app.services import course_service

        existing = MagicMock(id="c-1")
        mock_session.execute.return_value.scalar_one_or_none.return_value = existing
        got = await course_service.get_or_create_course(
            mock_session, "csit302", user_id="u-1", tier="free"
        )
        assert got is existing
        sql = str(mock_session.execute.await_args_list[0].args[0].compile())
        assert "courses.user_id" in sql
        assert "upper" in sql.lower()
        mock_session.add.assert_not_called()

    async def test_new_course_checks_quota_then_creates_for_owner(self, mock_session):
        from app.services import course_service

        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        with patch(
            "app.services.course_service.check_course_quota", new_callable=AsyncMock
        ) as quota:
            got = await course_service.get_or_create_course(
                mock_session, " csit302 ", user_id="u-1"
            )
        quota.assert_awaited_once()
        assert quota.await_args.args[1:] == ("u-1", "pro")
        assert got.code == "CSIT302"
        assert got.user_id == "u-1"
        mock_session.add.assert_called_once_with(got)

    async def test_quota_exceeded_creates_nothing(self, mock_session):
        from app.services import course_service

        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        with patch(
            "app.services.course_service.check_course_quota",
            new_callable=AsyncMock,
            side_effect=QuotaExceededError("courses", 3, "account"),
        ):
            with pytest.raises(QuotaExceededError):
                await course_service.get_or_create_course(
                    mock_session, "NEW", user_id="u-1", tier="free"
                )
        mock_session.add.assert_not_called()
