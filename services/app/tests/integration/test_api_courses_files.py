"""Course lifecycle (rename/archive/delete/merge), week views, file serving and review items.

Also the user-data-never-lost floor in practice: deleting a course removes its
database rows and, deliberately, leaves the stored files alone.
"""

from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.storage import get_storage
from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.chunk import Chunk
from app.models.course import Course
from app.models.flashcard import Flashcard
from app.models.review_item import ReviewItem
from app.models.summary import Summary

from ._support import make_docx, make_pdf, seed_course

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestCourseViews:
    async def test_list_detail_and_week_views(self, client_factory, make_user, db_session):
        user = await make_user()
        seeded = await seed_course(db_session, user.id, code="CV101")
        client = client_factory(user)

        listed = (await client.get("/api/courses")).json()
        assert [c["code"] for c in listed] == ["CV101"] and listed[0]["total_artifacts"] == 1

        detail = (await client.get("/api/courses/CV101")).json()
        assert detail["course"]["code"] == "CV101"
        week = detail["weeks"][0]
        assert week["week"] == 3
        assert (await client.get("/api/courses/NOPE")).status_code == 404

        wk = (await client.get("/api/courses/CV101/weeks/3")).json()
        assert wk["summary"]["id"] == seeded.summary.id
        assert [a["id"] for a in wk["artifacts"]] == [seeded.artifact.id]
        empty = (await client.get("/api/courses/CV101/weeks/9")).json()
        assert empty["summary"] is None and empty["artifacts"] == []
        assert (await client.get("/api/courses/NOPE/weeks/3")).status_code == 404

    async def test_courses_are_owner_scoped(self, client_factory, make_user, db_session):
        owner, stranger = await make_user(), await make_user()
        await seed_course(db_session, owner.id, code="CV202")
        other = client_factory(stranger)
        assert (await other.get("/api/courses")).json() == []
        for method, path in (
            ("GET", "/api/courses/CV202"),
            ("GET", "/api/courses/CV202/weeks/3"),
            ("PATCH", "/api/courses/CV202"),
            ("POST", "/api/courses/CV202/archive"),
            ("DELETE", "/api/courses/CV202"),
        ):
            kwargs = (
                {"json": {"name": "x"}}
                if method == "PATCH"
                else {"headers": {"X-Confirm": "CV202"}}
            )
            resp = await other.request(method, path, **kwargs)
            assert resp.status_code == 404, (method, path)
        assert [c["code"] for c in (await client_factory(owner).get("/api/courses")).json()] == [
            "CV202"
        ]

    @pytest.mark.xfail(
        strict=True,
        reason="BUG (floor 1): GET /courses/{code}/weeks/{n} loads the summary with "
        "summary_service.get_summary_for_week(), which matches on course code alone. Two users "
        "sharing a code hit MultipleResultsFound (500); when only the other user has a summary "
        "for that week it is returned to the wrong user",
    )
    async def test_week_detail_never_returns_another_users_summary(
        self, client_factory, make_user, db_session
    ):
        alice, bob = await make_user(), await make_user()
        await seed_course(db_session, alice.id, code="SHARED1", week=2)
        b = await seed_course(db_session, bob.id, code="SHARED1", week=2)
        b.summary.content_md = "BOB-ONLY"
        await db_session.flush()
        resp = await client_factory(alice).get("/api/courses/SHARED1/weeks/2")
        assert resp.status_code == 200
        assert "BOB-ONLY" not in resp.text


class TestCourseLifecycle:
    async def test_rename_conflict_and_archive(self, client_factory, make_user, db_session):
        user = await make_user()
        await seed_course(db_session, user.id, code="LC1")
        await seed_course(db_session, user.id, code="LC2")
        client = client_factory(user)

        renamed = await client.patch("/api/courses/LC1", json={"new_code": "LC9", "name": "Nine"})
        assert renamed.status_code == 200 and renamed.json()["code"] == "LC9"
        assert (await client.get("/api/courses/LC9")).status_code == 200
        assert (await client.get("/api/courses/LC1")).status_code == 404
        clash = await client.patch("/api/courses/LC9", json={"new_code": "LC2"})
        assert clash.status_code == 409
        assert (await client.patch("/api/courses/NOPE", json={"name": "x"})).status_code == 404

        archived = await client.post("/api/courses/LC2/archive")
        assert archived.json() == {"code": "LC2", "archived": True}
        assert [c["code"] for c in (await client.get("/api/courses")).json()] == ["LC9"]
        both = (await client.get("/api/courses", params={"include_archived": "true"})).json()
        assert {c["code"] for c in both} == {"LC9", "LC2"}
        assert (await client.post("/api/courses/NOPE/archive")).status_code == 404

    async def test_delete_requires_confirmation_removes_rows_but_keeps_files(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        seeded = await seed_course(db_session, user.id, code="DEL1")
        storage = get_storage()
        await storage.put(seeded.artifact.file_path, make_pdf())
        client = client_factory(user)

        assert (await client.delete("/api/courses/DEL1")).status_code == 428
        assert (
            await client.delete("/api/courses/DEL1", headers={"X-Confirm": "wrong"})
        ).status_code == 428
        assert (await client.get("/api/courses/DEL1")).status_code == 200  # still there

        resp = await client.delete("/api/courses/DEL1", headers={"X-Confirm": "DEL1"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["deleted"] is True
        assert resp.json()["counts"]["flashcards"] == 2 and resp.json()["counts"]["artifacts"] == 1

        assert (await client.get("/api/courses/DEL1")).status_code == 404
        for model, column, value in (
            (Course, Course.id, seeded.course.id),
            (LectureArtifact, LectureArtifact.id, seeded.artifact.id),
            (Summary, Summary.id, seeded.summary.id),
            (Chunk, Chunk.artifact_id, seeded.artifact.id),
            (Flashcard, Flashcard.course_id, seeded.course.id),
        ):
            assert (await db_session.execute(select(model).where(column == value))).first() is None
        # Floor: deleting a course must not delete the user's uploaded files.
        assert await storage.exists(seeded.artifact.file_path)

    async def test_http_merge_moves_content_and_archives_source(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        src = await seed_course(db_session, user.id, code="MRG1", week=1)
        dst = await seed_course(db_session, user.id, code="MRG2", week=2)
        client = client_factory(user)

        with patch("app.api.courses.resume_pipeline") as resume:
            resp = await client.post("/api/courses/MRG1/merge", json={"into": "MRG2"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["moved_summaries"] == 1 and resp.json()["conflict_weeks"] == []
        resume.assert_not_called()
        await db_session.refresh(src.artifact)
        assert src.artifact.course_id == dst.course.id
        listed = {c["code"] for c in (await client.get("/api/courses")).json()}
        assert listed == {"MRG2"}  # source archived

        assert (
            await client.post("/api/courses/MRG2/merge", json={"into": "MRG2"})
        ).status_code == 400
        assert (
            await client.post("/api/courses/NOPE/merge", json={"into": "MRG2"})
        ).status_code == 404
        assert (
            await client.post("/api/courses/MRG2/merge", json={"into": "X", "on_conflict": "bogus"})
        ).status_code == 422

    async def test_merge_cannot_target_another_users_course(
        self, client_factory, make_user, db_session
    ):
        owner, stranger = await make_user(), await make_user()
        await seed_course(db_session, owner.id, code="OWN1")
        await seed_course(db_session, stranger.id, code="THEIRS1")
        resp = await client_factory(owner).post("/api/courses/OWN1/merge", json={"into": "THEIRS1"})
        assert resp.status_code == 404


class TestFileServing:
    async def test_artifact_download_view_and_preview(self, client_factory, make_user, db_session):
        owner, stranger = await make_user(), await make_user()
        seeded = await seed_course(db_session, owner.id, code="FS1")
        pdf = make_pdf()
        await get_storage().put(seeded.artifact.file_path, pdf)
        client, other = client_factory(owner), client_factory(stranger)
        base = f"/api/files/uploads/artifacts/{seeded.artifact.id}"

        download = await client.get(base)
        assert download.status_code == 200 and download.content == pdf
        assert seeded.artifact.original_filename in download.headers["content-disposition"]
        view = await client.get(f"{base}/view")
        assert view.headers["content-type"] == "application/pdf"
        preview = await client.get(f"{base}/preview")
        assert preview.status_code == 200 and preview.content == pdf

        for suffix in ("", "/view", "/preview"):
            assert (await other.get(f"{base}{suffix}")).status_code == 404
        assert (await client.get("/api/files/uploads/artifacts/nope")).status_code == 404

    async def test_missing_blob_is_404_and_office_preview_rules(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        seeded = await seed_course(db_session, user.id, code="FS2")
        client = client_factory(user)
        base = f"/api/files/uploads/artifacts/{seeded.artifact.id}"
        assert (await client.get(base)).status_code == 404  # row exists, file does not

        seeded.artifact.file_type = "docx"
        await db_session.flush()
        await get_storage().put(seeded.artifact.file_path, make_docx())
        view = await client.get(f"{base}/view")
        assert "wordprocessingml" in view.headers["content-type"]
        with patch("app.services.preview_service._convert_to_pdf", return_value=None):
            failed = await client.get(f"{base}/preview")
        assert failed.status_code == 422

        seeded.artifact.file_type = "txt"
        await db_session.flush()
        assert (await client.get(f"{base}/preview")).status_code == 415

    async def test_office_preview_is_converted_once_and_cached(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        seeded = await seed_course(db_session, user.id, code="FS3")
        seeded.artifact.file_type = "pptx"
        await db_session.flush()
        await get_storage().put(seeded.artifact.file_path, b"pretend-pptx")
        calls = []

        async def fake_convert(src, out_dir):
            calls.append(src.name)
            out = out_dir / f"{src.stem}.pdf"
            out.write_bytes(make_pdf(["converted"]))
            return out

        client = client_factory(user)
        url = f"/api/files/uploads/artifacts/{seeded.artifact.id}/preview"
        with patch("app.services.preview_service._convert_to_pdf", fake_convert):
            first = await client.get(url)
            second = await client.get(url)
        assert first.status_code == second.status_code == 200
        assert calls == ["input.pptx"]  # the user's filename never reaches the converter
        assert first.content.startswith(b"%PDF")

    async def test_generic_route_serves_owned_summaries_and_blocks_others(
        self, client_factory, make_user, db_session
    ):
        owner, stranger = await make_user(), await make_user()
        seeded = await seed_course(db_session, owner.id, code="FS4")
        key = f"summaries/{seeded.course.id}/Week3.md"
        await get_storage().put(key, b"# private summary")
        client, other = client_factory(owner), client_factory(stranger)
        url = f"/api/files/summaries/{seeded.course.id}/Week3.md"

        ok = await client.get(url)
        assert ok.status_code == 200 and ok.content == b"# private summary"
        assert (await other.get(url)).status_code == 404
        assert (await client.get("/api/files/uploads/anything.pdf")).status_code == 400
        assert (await client.get("/api/files/summaries/..%2F..%2Fetc/passwd")).status_code in (
            403,
            404,
        )
        assert (await client.get(f"/api/files/summaries/{seeded.course.id}/../x")).status_code in (
            403,
            404,
        )
        assert (await client.get("/api/files/summaries/lonely.md")).status_code == 404

        art_key = f"extractions/{seeded.artifact.id}/manifest.json"
        await get_storage().put(art_key, b"{}")
        assert (
            await client.get(f"/api/files/extractions/{seeded.artifact.id}/manifest.json")
        ).status_code == 200
        assert (
            await other.get(f"/api/files/extractions/{seeded.artifact.id}/manifest.json")
        ).status_code == 404

    async def test_course_document_download_is_owner_scoped(
        self, client_factory, make_user, db_session
    ):
        from app.models.course_document import CourseDocument

        owner, stranger = await make_user(), await make_user()
        seeded = await seed_course(db_session, owner.id, code="FS5")
        key = f"courseops/{owner.id}/abc_outline.pdf"
        await get_storage().put(key, make_pdf())
        doc = CourseDocument(
            id=generate_id(),
            user_id=owner.id,
            course_id=seeded.course.id,
            document_type="outline",
            original_filename="outline.pdf",
            file_path=key,
            file_type="pdf",
            sha256="ab" * 32,
            file_size_bytes=10,
            status="processed",
        )
        db_session.add(doc)
        await db_session.flush()
        url = f"/api/files/courseops/documents/{doc.id}"
        ok = await client_factory(owner).get(url)
        assert ok.status_code == 200 and ok.headers["content-type"] == "application/pdf"
        assert (await client_factory(stranger).get(url)).status_code == 404


class TestReviewItems:
    async def _item(self, db_session, user, **kw):
        seeded = await seed_course(db_session, user.id, code=kw.pop("code", "RV1"))
        seeded.artifact.status = "waiting_review"
        item = ReviewItem(
            id=generate_id(),
            review_type="classification_course",
            entity_type="lecture_artifact",
            entity_id=seeded.artifact.id,
            payload_json={"context": "x"},
            suggested_values={"course_code": "RV9", "week": 5},
            status="pending",
        )
        db_session.add(item)
        await db_session.flush()
        return seeded, item

    async def test_list_get_resolve_and_resume(self, client_factory, make_user, db_session):
        user = await make_user()
        seeded, item = await self._item(db_session, user)
        db_session.add(Course(id=generate_id(), code="RV9", name="RV9", user_id=user.id))
        await db_session.flush()
        client = client_factory(user)

        pending = (await client.get("/api/review-items")).json()
        assert [i["id"] for i in pending] == [item.id]
        assert (await client.get(f"/api/review-items/{item.id}")).json()["status"] == "pending"
        assert (await client.get("/api/review-items", params={"status": "resolved"})).json() == []

        with patch("app.api.review_items.resume_pipeline") as resume:
            resp = await client.post(
                f"/api/review-items/{item.id}/resolve",
                json={"resolution": {"course_code": "RV9", "week": 5, "title": "Fixed"}},
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "resolved"
        resume.assert_called_once()
        assert resume.call_args.kwargs["from_stage"] == "extract"
        await db_session.refresh(seeded.artifact)
        assert seeded.artifact.week == 5 and seeded.artifact.title == "Fixed"
        assert seeded.artifact.status == "classified"
        again = await client.post(f"/api/review-items/{item.id}/resolve", json={"resolution": {}})
        assert again.status_code == 400  # already resolved

    async def test_dismiss_and_scoping(self, client_factory, make_user, db_session):
        owner, stranger = await make_user(), await make_user()
        seeded, item = await self._item(db_session, owner)
        other = client_factory(stranger)
        assert (await other.get(f"/api/review-items/{item.id}")).status_code == 404
        assert (await other.get("/api/review-items")).json() == []
        assert (
            await other.post(
                f"/api/review-items/{item.id}/resolve", json={"resolution": {"week": 1}}
            )
        ).status_code == 404
        assert (await other.post(f"/api/review-items/{item.id}/dismiss")).status_code == 400

        dismissed = await client_factory(owner).post(f"/api/review-items/{item.id}/dismiss")
        assert dismissed.status_code == 200 and dismissed.json()["status"] == "dismissed"
        await db_session.refresh(seeded.artifact)
        assert seeded.artifact.status == "waiting_review"  # dismiss changes nothing else

    async def test_unresolvable_entity_types_are_rejected(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        seeded, item = await self._item(db_session, user)
        item.entity_type = "merge_week_conflict"
        await db_session.flush()
        resp = await client_factory(user).post(
            f"/api/review-items/{item.id}/resolve", json={"resolution": {}}
        )
        assert resp.status_code in (400, 404)
