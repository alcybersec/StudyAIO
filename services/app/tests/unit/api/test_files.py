"""Tests for the file serving API endpoints."""

import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.storage import get_storage, reset_storage

OWNER_A = "owner-a-user-id"


@pytest.mark.asyncio
class TestViewArtifact:
    """Tests for GET /api/files/uploads/artifacts/{id}/view."""

    async def test_view_pdf_returns_correct_mime_type(self, async_client, tmp_path):
        """View endpoint serves PDF with application/pdf content type."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake pdf content")

        mock_artifact = AsyncMock()
        mock_artifact.file_path = str(pdf_file)
        mock_artifact.file_type = "pdf"
        mock_artifact.original_filename = "lecture.pdf"

        with patch(
            "app.api.files.artifact_service.get_artifact",
            return_value=mock_artifact,
        ):
            response = await async_client.get("/api/files/uploads/artifacts/art-001/view")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        # Should NOT have content-disposition: attachment
        assert "attachment" not in response.headers.get("content-disposition", "")

    async def test_view_docx_returns_correct_mime_type(self, async_client, tmp_path):
        """View endpoint serves DOCX with correct content type."""
        docx_file = tmp_path / "test.docx"
        docx_file.write_bytes(b"PK fake docx")

        mock_artifact = AsyncMock()
        mock_artifact.file_path = str(docx_file)
        mock_artifact.file_type = "docx"
        mock_artifact.original_filename = "lecture.docx"

        with patch(
            "app.api.files.artifact_service.get_artifact",
            return_value=mock_artifact,
        ):
            response = await async_client.get("/api/files/uploads/artifacts/art-002/view")

        assert response.status_code == 200
        content_type = response.headers["content-type"]
        assert "officedocument.wordprocessingml" in content_type

    async def test_view_pptx_returns_correct_mime_type(self, async_client, tmp_path):
        """View endpoint serves PPTX with correct content type."""
        pptx_file = tmp_path / "test.pptx"
        pptx_file.write_bytes(b"PK fake pptx")

        mock_artifact = AsyncMock()
        mock_artifact.file_path = str(pptx_file)
        mock_artifact.file_type = "pptx"
        mock_artifact.original_filename = "lecture.pptx"

        with patch(
            "app.api.files.artifact_service.get_artifact",
            return_value=mock_artifact,
        ):
            response = await async_client.get("/api/files/uploads/artifacts/art-003/view")

        assert response.status_code == 200
        content_type = response.headers["content-type"]
        assert "officedocument.presentationml" in content_type

    async def test_view_artifact_not_found(self, async_client):
        """View returns 404 when artifact doesn't exist."""
        with patch(
            "app.api.files.artifact_service.get_artifact",
            return_value=None,
        ):
            response = await async_client.get("/api/files/uploads/artifacts/nonexistent/view")

        assert response.status_code == 404
        assert "Artifact not found" in response.json()["detail"]

    async def test_view_artifact_file_missing_on_disk(self, async_client):
        """View returns 404 when artifact exists but file is gone."""
        mock_artifact = AsyncMock()
        mock_artifact.file_path = "/nonexistent/path/file.pdf"
        mock_artifact.file_type = "pdf"

        with patch(
            "app.api.files.artifact_service.get_artifact",
            return_value=mock_artifact,
        ):
            response = await async_client.get("/api/files/uploads/artifacts/art-004/view")

        assert response.status_code == 404
        assert "File not found" in response.json()["detail"]

    async def test_view_unknown_type_falls_back_to_octet_stream(self, async_client, tmp_path):
        """View serves unknown file types as octet-stream."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("hello")

        mock_artifact = AsyncMock()
        mock_artifact.file_path = str(txt_file)
        mock_artifact.file_type = "txt"
        mock_artifact.original_filename = "notes.txt"

        with patch(
            "app.api.files.artifact_service.get_artifact",
            return_value=mock_artifact,
        ):
            response = await async_client.get("/api/files/uploads/artifacts/art-005/view")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/octet-stream"


@pytest.mark.asyncio
class TestDownloadArtifact:
    """Tests for GET /api/files/uploads/artifacts/{id} (download)."""

    async def test_download_returns_attachment_header(self, async_client, tmp_path):
        """Download endpoint includes content-disposition attachment."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake pdf")

        mock_artifact = AsyncMock()
        mock_artifact.file_path = str(pdf_file)
        mock_artifact.file_type = "pdf"
        mock_artifact.original_filename = "CSIT302_Week5.pdf"

        with patch(
            "app.api.files.artifact_service.get_artifact",
            return_value=mock_artifact,
        ):
            response = await async_client.get("/api/files/uploads/artifacts/art-001")

        assert response.status_code == 200
        assert "attachment" in response.headers.get("content-disposition", "")


@pytest.mark.asyncio
class TestDownloadCourseDocument:
    """Tests for GET /api/files/courseops/documents/{id}."""

    async def test_download_returns_attachment(self, async_client, tmp_path):
        """Serves a course document by ID with an attachment header."""
        pdf_file = tmp_path / "brief.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 brief")

        mock_doc = AsyncMock()
        mock_doc.file_path = str(pdf_file)
        mock_doc.file_type = "pdf"
        mock_doc.original_filename = "Assignment3_brief.pdf"

        with patch(
            "app.services.courseops_service.get_course_document",
            new=AsyncMock(return_value=mock_doc),
        ):
            response = await async_client.get("/api/files/courseops/documents/doc-001")

        assert response.status_code == 200
        assert "attachment" in response.headers.get("content-disposition", "")

    async def test_download_404_when_missing(self, async_client):
        """Unknown document yields 404."""
        with patch(
            "app.services.courseops_service.get_course_document",
            new=AsyncMock(return_value=None),
        ):
            response = await async_client.get("/api/files/courseops/documents/nope")
        assert response.status_code == 404

    async def test_download_scoped_to_owner_returns_404_for_other_user(
        self, async_client, default_test_user
    ):
        """IDOR regression (#47): user B gets 404 for user A's document id.

        The download endpoint must thread the authenticated user's id into the
        owner-scoped lookup. Here the document belongs to owner-A while the
        authenticated caller is default_test_user (user B), so the scoped
        service returns None → 404, matching the artifact path (no 403 oracle).
        """
        owner_a_doc = AsyncMock()
        owner_a_doc.file_path = "uploads/secret.pdf"
        owner_a_doc.file_type = "pdf"
        owner_a_doc.original_filename = "owner_a_secret.pdf"

        async def scoped_get(session, document_id, user_id=None):
            # Emulate the real owner filter: only owner-A may retrieve it.
            return owner_a_doc if user_id == "owner-A" else None

        mock_get = AsyncMock(side_effect=scoped_get)
        with patch("app.services.courseops_service.get_course_document", new=mock_get):
            response = await async_client.get("/api/files/courseops/documents/doc-owned-by-a")

        assert response.status_code == 404
        # Wiring assertion: the endpoint must pass the caller's own id, not
        # nothing — otherwise the scope is silently bypassed.
        assert mock_get.await_args.kwargs.get("user_id") == default_test_user.id
        assert default_test_user.id != "owner-A"


@pytest.mark.asyncio
class TestPreviewArtifact:
    """Tests for GET /api/files/uploads/artifacts/{id}/preview (pptx/docx → pdf)."""

    async def test_pptx_preview_serves_converted_pdf(
        self, async_client, tmp_path, default_test_user
    ):
        pdf_file = tmp_path / "converted.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 converted")
        art = AsyncMock()
        art.file_type = "pptx"
        art.file_path = "uploads/x.pptx"
        mock_ensure = AsyncMock(return_value=str(pdf_file))
        with (
            patch("app.api.files.artifact_service.get_artifact", return_value=art) as mock_get,
            patch("app.services.preview_service.ensure_preview_pdf", new=mock_ensure),
        ):
            response = await async_client.get("/api/files/uploads/artifacts/a1/preview")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/pdf")
        # Both id-addressed lookups carry the caller. The conversion cache is
        # keyed on artifact_id, so an unscoped ensure_preview_pdf would serve a
        # rendered copy of another user's deck even once get_artifact was fixed.
        assert mock_get.await_args.kwargs.get("user_id") == default_test_user.id
        assert mock_ensure.await_args.kwargs.get("user_id") == default_test_user.id

    async def test_pdf_preview_serves_original(self, async_client, tmp_path):
        pdf_file = tmp_path / "orig.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 orig")
        art = AsyncMock()
        art.file_type = "pdf"
        art.file_path = str(pdf_file)
        with patch("app.api.files.artifact_service.get_artifact", return_value=art):
            response = await async_client.get("/api/files/uploads/artifacts/a1/preview")
        assert response.status_code == 200

    async def test_unsupported_type_returns_415(self, async_client):
        art = AsyncMock()
        art.file_type = "xlsx"
        with patch("app.api.files.artifact_service.get_artifact", return_value=art):
            response = await async_client.get("/api/files/uploads/artifacts/a1/preview")
        assert response.status_code == 415

    async def test_conversion_failure_returns_422(self, async_client):
        art = AsyncMock()
        art.file_type = "docx"
        art.file_path = "uploads/x.docx"
        with (
            patch("app.api.files.artifact_service.get_artifact", return_value=art),
            patch(
                "app.services.preview_service.ensure_preview_pdf",
                new=AsyncMock(return_value=None),
            ),
        ):
            response = await async_client.get("/api/files/uploads/artifacts/a1/preview")
        assert response.status_code == 422

    async def test_missing_artifact_returns_404(self, async_client):
        with patch("app.api.files.artifact_service.get_artifact", return_value=None):
            response = await async_client.get("/api/files/uploads/artifacts/nope/preview")
        assert response.status_code == 404


# ── #66: the generic path-addressed route ─────────────────────────────
#
# ``GET /api/files/{file_type}/{path}`` shipped with no auth dependency at
# all while every sibling route in this module had one, and was confirmed
# live against the production instance serving generated summaries and
# original lecture uploads to anonymous callers. Summary keys are
# ``summaries/<CODE>/<CODE>_Week<N>.md``, so the corpus was enumerable from a
# guessed course code.
#
# Authentication alone would not have been enough: the path carries no owner,
# so any signed-in user could still read anyone else's files. Each scoping
# test below therefore asserts the 404 *and* that the caller's own id reached
# the scoped lookup -- the wiring assertion that caught the #47/PR #50 revert
# when the plain status assertion did not.


@pytest.fixture
async def anon_client(mock_session):
    """A client with no identity, and the self-hosted fallback turned off.

    The shared ``async_client`` overrides ``get_current_user_or_default``, so
    it can never observe a request being rejected -- it always has a user.
    This one overrides only the session, leaving the real auth dependency in
    place, and sets ``self_hosted=False`` so an anonymous caller is a rejected
    caller rather than the default admin.
    """
    from app.core.database import get_session
    from app.main import app

    async def override_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_session
    with (
        tempfile.TemporaryDirectory() as tmpdir,
        patch("app.config.settings.data_dir", tmpdir),
        patch("app.config.settings.self_hosted", False),
    ):
        reset_storage()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client
        reset_storage()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
class TestServeFileRequiresAuth:
    """#66: the route must not serve anything to an anonymous caller.

    Each test writes the file first, so the reject is a real reject and not
    the 404 of a file that was never there -- the vulnerable route serves
    these with a 200.
    """

    async def test_extraction_image_rejects_anonymous(self, anon_client):
        """The exact shape the summary renderer requests, with no cookie."""
        await get_storage().put("extractions/art-001/images/page1_img1.png", b"\x89PNG fake")
        response = await anon_client.get("/api/files/extractions/art-001/images/page1_img1.png")
        assert response.status_code == 401

    async def test_summary_rejects_anonymous(self, anon_client):
        """The enumerable shape from the issue, with no cookie."""
        await get_storage().put("summaries/CSCI302/CSCI302_Week9.md", b"# CSCI302 - Week 9\n")
        response = await anon_client.get("/api/files/summaries/CSCI302/CSCI302_Week9.md")
        assert response.status_code == 401
        assert b"CSCI302" not in response.content

    async def test_anonymous_rejection_precedes_the_prefix_check(self, anon_client):
        """Auth runs as a dependency, so even a rejected prefix 401s first.

        If this ever returns 400 the identity check has moved into the handler
        body, which would make the route an existence oracle again.
        """
        response = await anon_client.get("/api/files/uploads/whatever.pptx")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestServeExtractionScoping:
    """#66: ``extractions/<artifact_id>/...`` scopes on the artifact's owner."""

    async def test_404_for_another_users_artifact(self, async_client, default_test_user):
        """User B must not read the images extracted from user A's lecture."""
        await get_storage().put(
            "extractions/art-owned-by-a/images/page1_img1.png", b"\x89PNG owner-a"
        )

        async def scoped(session, artifact_id, user_id=None):
            return MagicMock() if user_id == OWNER_A else None

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.files.artifact_service.get_artifact", new=mock):
            response = await async_client.get(
                "/api/files/extractions/art-owned-by-a/images/page1_img1.png"
            )

        assert response.status_code == 404
        # Wiring: the endpoint must hand the scoped getter the caller's own
        # id. Without this assertion a revert to an unscoped lookup still
        # returns 404 here, because the mock returns None either way.
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id
        assert default_test_user.id != OWNER_A

    async def test_owner_is_served_their_own_extraction_image(
        self, async_client, default_test_user
    ):
        """The image the summary renderer embeds still loads for its owner."""
        key = "extractions/art-owned-by-me/images/page1_img1.png"
        await get_storage().put(key, b"\x89PNG\r\n\x1a\n fake image bytes")

        async def scoped(session, artifact_id, user_id=None):
            return MagicMock() if user_id == default_test_user.id else None

        with patch(
            "app.api.files.artifact_service.get_artifact", new=AsyncMock(side_effect=scoped)
        ):
            response = await async_client.get(f"/api/files/{key}")

        assert response.status_code == 200
        assert response.content == b"\x89PNG\r\n\x1a\n fake image bytes"

    async def test_path_without_an_owner_segment_is_404(self, async_client):
        """``extractions/<file>`` names no artifact, so nothing authorises it.

        The file is written first: an unresolvable path must be refused
        because no owner can be established, not merely because it is absent.
        """
        await get_storage().put("extractions/loose_file.png", b"\x89PNG loose")

        mock = AsyncMock(return_value=MagicMock())
        with patch("app.api.files.artifact_service.get_artifact", new=mock):
            response = await async_client.get("/api/files/extractions/loose_file.png")

        assert response.status_code == 404
        mock.assert_not_awaited()


@pytest.mark.asyncio
class TestServeSummaryScoping:
    """#66: ``summaries/<COURSE_CODE>/...`` scopes on the course's owner.

    This is the half that was enumerable -- course codes are standard
    university codes and week numbers run 1-15.
    """

    async def test_404_for_another_users_course(self, async_client, default_test_user):
        """The exact request from the issue must not return user A's summary."""
        await get_storage().put(
            "summaries/CSCI302/CSCI302_Week9.md", b"# CSCI302 - Week 9: Threat Intelligence\n"
        )

        async def scoped(session, code, user_id=None):
            return MagicMock() if user_id == OWNER_A else None

        mock = AsyncMock(side_effect=scoped)
        with patch("app.api.files.course_service.get_course_by_code", new=mock):
            response = await async_client.get("/api/files/summaries/CSCI302/CSCI302_Week9.md")

        assert response.status_code == 404
        assert b"Threat Intelligence" not in response.content
        assert mock.await_args.kwargs.get("user_id") == default_test_user.id
        assert default_test_user.id != OWNER_A

    async def test_owner_is_served_their_own_summary(self, async_client, default_test_user):
        key = "summaries/CSCI302/CSCI302_Week9.md"
        await get_storage().put(key, b"# CSCI302 - Week 9\n")

        async def scoped(session, code, user_id=None):
            return MagicMock() if user_id == default_test_user.id else None

        with patch(
            "app.api.files.course_service.get_course_by_code", new=AsyncMock(side_effect=scoped)
        ):
            response = await async_client.get(f"/api/files/{key}")

        assert response.status_code == 200
        assert response.content == b"# CSCI302 - Week 9\n"

    async def test_scoped_lookup_receives_the_course_code_from_the_path(self, async_client):
        """The first path segment, not some other part of the key, is the owner."""
        mock = AsyncMock(return_value=None)
        with patch("app.api.files.course_service.get_course_by_code", new=mock):
            await async_client.get("/api/files/summaries/CSCI302/CSCI302_Week9.md")

        assert mock.await_args.args[1] == "CSCI302"


@pytest.mark.asyncio
class TestServeFileDroppedPrefixes:
    """#66: ``uploads`` and ``courseops`` are no longer path-addressable.

    Both have owner-scoped id-addressed routes that the UI already uses, and
    an uploads key carries no owner segment to scope by.
    """

    async def test_uploads_by_raw_path_is_rejected(self, async_client):
        """The lecture download from the issue, by raw path, with the file present."""
        name = "0192abcd-dead-beef-cafe-000000000001_CSIT242_Week 6.pptx"
        await get_storage().put(f"uploads/{name}", b"PK fake pptx")

        response = await async_client.get(
            "/api/files/uploads/0192abcd-dead-beef-cafe-000000000001_CSIT242_Week%206.pptx"
        )
        assert response.status_code == 400
        assert b"PK fake pptx" not in response.content

    async def test_courseops_by_raw_path_is_rejected(self, async_client):
        await get_storage().put("courseops/some-course/brief.pdf", b"%PDF-1.4 brief")

        response = await async_client.get("/api/files/courseops/some-course/brief.pdf")
        assert response.status_code == 400
        assert b"%PDF" not in response.content

    async def test_a_prefix_with_no_ownership_rule_fails_closed(self, default_test_user):
        """``_authorize_path`` must refuse a prefix it has no rule for.

        Unreachable over HTTP today because ``_VALID_PREFIXES`` gates it, but
        the set and the dispatch are edited independently: adding a prefix to
        the set without adding a branch must deny, not silently inherit
        whichever branch happens to be last.
        """
        from fastapi import HTTPException

        from app.api.files import _authorize_path

        with pytest.raises(HTTPException) as excinfo:
            await _authorize_path("uploads", "some/file.pptx", default_test_user, AsyncMock())

        assert excinfo.value.status_code == 404

    async def test_id_addressed_uploads_route_still_wins(self, async_client, tmp_path):
        """Dropping the prefix must not shadow ``/uploads/artifacts/{id}``."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 still here")

        art = AsyncMock()
        art.file_path = str(pdf_file)
        art.file_type = "pdf"
        art.original_filename = "lecture.pdf"

        with patch("app.api.files.artifact_service.get_artifact", return_value=art):
            response = await async_client.get("/api/files/uploads/artifacts/art-001")

        assert response.status_code == 200


@pytest.mark.asyncio
class TestServeFileTraversal:
    """Pin the traversal block that predates #66, so the rewrite kept it."""

    async def test_traversal_is_blocked_before_any_lookup(self, async_client):
        """``..`` is refused without the scoped getter ever being consulted."""
        mock = AsyncMock(return_value=MagicMock())
        with patch("app.api.files.artifact_service.get_artifact", new=mock):
            response = await async_client.get(
                "/api/files/extractions/art-001/%2E%2E/%2E%2E/%2E%2E/etc/passwd"
            )

        assert response.status_code == 403
        mock.assert_not_awaited()

    async def test_traversal_blocked_on_summaries(self, async_client):
        mock = AsyncMock(return_value=MagicMock())
        with patch("app.api.files.course_service.get_course_by_code", new=mock):
            response = await async_client.get(
                "/api/files/summaries/CSCI302/%2E%2E/%2E%2E/uploads/secret.pptx"
            )

        assert response.status_code == 403
        mock.assert_not_awaited()
