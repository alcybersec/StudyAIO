"""CourseOps: documents, assessments, deadlines, exports and the extraction task.

HTTP paths run on the real cookie chain with two users so every by-id route is
checked for owner scoping. The extraction task is run against committed rows
with a fake agent, the way the worker runs it.
"""

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app.core.database import async_session_factory
from app.core.exceptions import CourseOpsError
from app.core.storage import get_storage
from app.core.utils import generate_id
from app.models.assessment import Assessment
from app.models.course import Course
from app.models.course_document import CourseDocument
from app.models.deadline import Deadline
from app.models.exam import Exam
from app.models.user import User
from app.pipeline.courseops_task import _process_document
from app.services import account_service

from ._support import FakeAgent, make_docx, make_pdf

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture
def task_mock():
    with patch("app.pipeline.courseops_task.process_course_document", MagicMock()) as mock:
        yield mock


async def _course(db_session, user, code="OPS101") -> Course:
    course = Course(id=generate_id(), code=code, name=code, user_id=user.id)
    db_session.add(course)
    await db_session.flush()
    return course


class TestDocuments:
    async def test_upload_list_get_and_delete_document(
        self, client_factory, make_user, db_session, task_mock
    ):
        user = await make_user()
        await _course(db_session, user)
        client = client_factory(user)
        content = make_pdf(["Course outline: midterm in week 6"])

        resp = await client.post(
            "/api/courseops/documents",
            params={"course_code": "OPS101", "document_type": "outline"},
            files={"file": ("outline.pdf", content, "application/pdf")},
        )
        assert resp.status_code == 201, resp.text
        doc = resp.json()
        assert doc["status"] == "pending" and doc["document_type"] == "outline"
        task_mock.delay.assert_called_once_with(doc["id"])

        row = (
            await db_session.execute(select(CourseDocument).where(CourseDocument.id == doc["id"]))
        ).scalar_one()
        assert row.user_id == user.id
        assert await get_storage().get(row.file_path) == content

        listed = await client.get("/api/courseops/documents", params={"course_code": "OPS101"})
        assert [d["id"] for d in listed.json()] == [doc["id"]]
        detail = await client.get(f"/api/courseops/documents/{doc['id']}")
        assert detail.status_code == 200 and detail.json()["assessments"] == []

        dup = await client.post(
            "/api/courseops/documents",
            params={"course_code": "OPS101", "document_type": "outline"},
            files={"file": ("again.pdf", content, "application/pdf")},
        )
        assert dup.status_code == 409

        assert (await client.delete(f"/api/courseops/documents/{doc['id']}")).status_code == 204
        assert await get_storage().exists(row.file_path) is False  # last reference, blob removed
        assert (await client.get(f"/api/courseops/documents/{doc['id']}")).status_code == 404

    async def test_upload_validation(self, client_factory, make_user, db_session, task_mock):
        user = await make_user()
        await _course(db_session, user)
        client = client_factory(user)
        bad_ext = await client.post(
            "/api/courseops/documents",
            params={"course_code": "OPS101", "document_type": "outline"},
            files={"file": ("x.txt", b"hi", "text/plain")},
        )
        assert bad_ext.status_code == 400
        bad_type = await client.post(
            "/api/courseops/documents",
            params={"course_code": "OPS101", "document_type": "memo"},
            files={"file": ("x.pdf", make_pdf(), "application/pdf")},
        )
        assert bad_type.status_code == 400
        no_course = await client.post(
            "/api/courseops/documents",
            params={"course_code": "NOPE", "document_type": "outline"},
            files={"file": ("x.pdf", make_pdf(), "application/pdf")},
        )
        assert no_course.status_code == 409
        task_mock.delay.assert_not_called()

    async def test_documents_are_owner_scoped(
        self, client_factory, make_user, db_session, task_mock
    ):
        owner, stranger = await make_user(), await make_user()
        await _course(db_session, owner)
        up = await client_factory(owner).post(
            "/api/courseops/documents",
            params={"course_code": "OPS101", "document_type": "handbook"},
            files={"file": ("h.pdf", make_pdf(), "application/pdf")},
        )
        doc_id = up.json()["id"]
        other = client_factory(stranger)
        assert (await other.get(f"/api/courseops/documents/{doc_id}")).status_code == 404
        assert (await other.delete(f"/api/courseops/documents/{doc_id}")).status_code == 404
        listed = await other.get("/api/courseops/documents", params={"course_code": "OPS101"})
        assert listed.json() == []
        # The stranger's attempts left the owner's document and blob intact.
        assert (
            await client_factory(owner).get(f"/api/courseops/documents/{doc_id}")
        ).status_code == 200

    async def test_assessment_documents_attach_list_and_scope(
        self, client_factory, make_user, db_session
    ):
        owner, stranger = await make_user(), await make_user()
        course = await _course(db_session, owner)
        assessment = Assessment(
            id=generate_id(), course_id=course.id, title="Project", assessment_type="project"
        )
        db_session.add(assessment)
        await db_session.flush()

        client = client_factory(owner)
        ok = await client.post(
            f"/api/courseops/assessments/{assessment.id}/documents",
            params={"document_type": "rubric"},
            files={"file": ("rubric.docx", make_docx(), "application/octet-stream")},
        )
        assert ok.status_code == 201, ok.text
        assert ok.json()["assessment_id"] == assessment.id
        listed = await client.get(f"/api/courseops/assessments/{assessment.id}/documents")
        assert len(listed.json()) == 1

        other = client_factory(stranger)
        assert (
            await other.get(f"/api/courseops/assessments/{assessment.id}/documents")
        ).json() == []

        bad = await client.post(
            f"/api/courseops/assessments/{assessment.id}/documents",
            params={"document_type": "meme"},
            files={"file": ("a.pdf", make_pdf(), "application/pdf")},
        )
        assert bad.status_code == 400
        bad_ext = await client.post(
            f"/api/courseops/assessments/{assessment.id}/documents",
            files={"file": ("a.exe", b"x", "application/octet-stream")},
        )
        assert bad_ext.status_code == 400

    async def test_stranger_cannot_attach_document_to_anothers_assessment(
        self, client_factory, make_user, db_session
    ):
        owner, stranger = await make_user(), await make_user()
        course = await _course(db_session, owner)
        assessment = Assessment(
            id=generate_id(), course_id=course.id, title="Project", assessment_type="project"
        )
        db_session.add(assessment)
        await db_session.flush()

        denied = await client_factory(stranger).post(
            f"/api/courseops/assessments/{assessment.id}/documents",
            files={"file": ("rubric.docx", make_docx(["different"]), "application/octet-stream")},
        )
        assert denied.status_code == 404
        # Nothing was written against the owner's assessment (a foreign row there
        # would also block the owner's account deletion by FK).
        rows = await db_session.execute(
            select(CourseDocument).where(CourseDocument.assessment_id == assessment.id)
        )
        assert rows.scalars().all() == []


class TestAssessmentsAndDeadlines:
    async def test_assessment_crud_and_scoping(self, client_factory, make_user, db_session):
        owner, stranger = await make_user(), await make_user()
        await _course(db_session, owner)
        client, other = client_factory(owner), client_factory(stranger)

        created = await client.post(
            "/api/courseops/assessments",
            params={"course_code": "OPS101"},
            json={
                "title": "Midterm",
                "assessment_type": "exam",
                "weight_pct": 30,
                "weeks_relevant": [1, 2],
            },
        )
        assert created.status_code == 201
        aid = created.json()["id"]
        assert created.json()["weight_pct"] == 30

        assert (
            await other.post(
                "/api/courseops/assessments",
                params={"course_code": "OPS101"},
                json={"title": "Hijack"},
            )
        ).status_code == 404
        updated = await client.patch(
            f"/api/courseops/assessments/{aid}", json={"title": "Midterm 1", "weight_pct": 35}
        )
        assert updated.json()["title"] == "Midterm 1" and updated.json()["weight_pct"] == 35
        assert (
            await other.patch(f"/api/courseops/assessments/{aid}", json={"title": "Stolen"})
        ).status_code == 404
        assert (
            await client.patch(f"/api/courseops/assessments/{aid}", json={"weight_pct": 150})
        ).status_code == 422

        listed = await client.get("/api/courseops/assessments", params={"course_code": "OPS101"})
        assert [a["title"] for a in listed.json()] == ["Midterm 1"]
        assert (
            await other.get("/api/courseops/assessments", params={"course_code": "OPS101"})
        ).json() == []

    async def test_deadline_lifecycle_and_scoping(self, client_factory, make_user, db_session):
        owner, stranger = await make_user(), await make_user()
        await _course(db_session, owner)
        client, other = client_factory(owner), client_factory(stranger)
        soon = (date.today() + timedelta(days=5)).isoformat()
        past = (date.today() - timedelta(days=5)).isoformat()

        d1 = await client.post(
            "/api/courseops/deadlines",
            params={"course_code": "OPS101"},
            json={"title": "Assignment 1", "due_date": soon, "deadline_type": "assignment"},
        )
        d2 = await client.post(
            "/api/courseops/deadlines",
            params={"course_code": "OPS101"},
            json={"title": "Old quiz", "due_date": past},
        )
        assert d1.status_code == d2.status_code == 201
        assert d1.json()["is_confirmed"] is True

        everything = await client.get("/api/courseops/deadlines", params={"course_code": "OPS101"})
        assert len(everything.json()) == 2
        upcoming = await client.get(
            "/api/courseops/deadlines", params={"course_code": "OPS101", "upcoming": "true"}
        )
        assert [d["title"] for d in upcoming.json()] == ["Assignment 1"]

        did = d1.json()["id"]
        edited = await client.put(
            f"/api/courseops/deadlines/{did}", json={"title": "Assignment One"}
        )
        assert edited.json()["title"] == "Assignment One"
        assert (
            await other.put(f"/api/courseops/deadlines/{did}", json={"title": "x"})
        ).status_code == 404
        assert (await other.delete(f"/api/courseops/deadlines/{did}")).status_code == 404
        assert (
            await other.post(
                "/api/courseops/deadlines",
                params={"course_code": "OPS101"},
                json={"title": "x", "due_date": soon},
            )
        ).status_code == 404

        assert (await client.delete(f"/api/courseops/deadlines/{did}")).status_code == 204
        assert (await client.delete(f"/api/courseops/deadlines/{did}")).status_code == 404

    async def test_create_exam_from_deadline(self, client_factory, make_user, db_session):
        owner, stranger = await make_user(), await make_user()
        course = await _course(db_session, owner)
        assessment = Assessment(
            id=generate_id(),
            course_id=course.id,
            title="Final",
            assessment_type="exam",
            weeks_relevant=[3, 4],
        )
        db_session.add(assessment)
        await db_session.flush()
        deadline = Deadline(
            id=generate_id(),
            course_id=course.id,
            assessment_id=assessment.id,
            title="Final exam",
            due_date=date.today() + timedelta(days=30),
            deadline_type="exam",
            is_confirmed=False,
        )
        db_session.add(deadline)
        await db_session.flush()

        assert (
            await client_factory(stranger).post(
                f"/api/courseops/deadlines/{deadline.id}/create-exam"
            )
        ).status_code == 404
        await db_session.refresh(deadline)
        assert deadline.is_confirmed is False  # the stranger's attempt changed nothing

        resp = await client_factory(owner).post(
            f"/api/courseops/deadlines/{deadline.id}/create-exam"
        )
        assert resp.status_code == 201, resp.text
        exam = (
            await db_session.execute(select(Exam).where(Exam.id == resp.json()["exam_id"]))
        ).scalar_one()
        assert exam.user_id == owner.id and exam.weeks_scope == [3, 4]
        await db_session.refresh(deadline)
        assert deadline.is_confirmed is True

        missing = await client_factory(owner).post("/api/courseops/deadlines/nope/create-exam")
        assert missing.status_code == 404

    async def test_calendar_and_task_plan_exports(self, client_factory, make_user, db_session):
        owner, stranger = await make_user(), await make_user()
        course = await _course(db_session, owner)
        db_session.add(
            Deadline(
                id=generate_id(),
                course_id=course.id,
                title="Lab report",
                due_date=date.today() + timedelta(days=9),
                deadline_type="assignment",
                is_confirmed=True,
            )
        )
        await db_session.flush()

        ics = await client_factory(owner).get("/api/courseops/export/calendar/OPS101")
        assert ics.status_code == 200 and ics.headers["content-type"].startswith("text/calendar")
        assert "BEGIN:VCALENDAR" in ics.text and "Lab report" in ics.text
        plan = await client_factory(owner).get("/api/courseops/export/task-plan/OPS101")
        assert plan.status_code == 200 and "Lab report" in plan.text

        # Another user's request for the same course code finds nothing.
        assert (
            await client_factory(stranger).get("/api/courseops/export/calendar/OPS101")
        ).status_code == 404
        assert (
            await client_factory(stranger).get("/api/courseops/export/task-plan/OPS101")
        ).status_code == 404


@pytest_asyncio.fixture(loop_scope="session")
async def committed_doc():
    """A committed user, course and PDF document; removed afterwards."""
    uid = generate_id()
    async with async_session_factory() as session:
        session.add(
            User(
                id=uid,
                email=f"ops-{uid[-10:]}@example.com",
                username=f"ops_{uid[-10:]}",
                role="user",
                tier="free",
                is_active=True,
                email_verified=True,
                mfa_enabled=False,
            )
        )
        await session.flush()
        course = Course(id=generate_id(), code="OPSX1", name="OPSX1", user_id=uid)
        session.add(course)
        await session.flush()

        async def make_doc(content: bytes, name: str = "outline.pdf", ftype: str = "pdf") -> str:
            key = f"courseops/{uid}/{generate_id()[:8]}_{name}"
            await get_storage().put(key, content)
            doc = CourseDocument(
                id=generate_id(),
                user_id=uid,
                course_id=course.id,
                document_type="outline",
                title=name,
                original_filename=name,
                file_path=key,
                file_type=ftype,
                sha256=generate_id().replace("-", "") * 2,
                file_size_bytes=len(content),
                status="pending",
            )
            session.add(doc)
            await session.commit()
            return doc.id

        yield SimpleNamespace(uid=uid, course_id=course.id, make_doc=make_doc)
    async with async_session_factory() as session:
        # delete_user_account cannot yet remove a user who owns course documents or
        # assessments (see test_account_deletion_courseops.py), so clear them first.
        for table in ("deadlines", "assessments", "course_documents"):
            await session.execute(
                text(
                    f"DELETE FROM {table} WHERE course_id IN (SELECT id FROM courses WHERE user_id = :u)"
                ),
                {"u": uid},
            )
        await session.commit()
        await account_service.delete_user_account(session, uid)
        await session.commit()


class TestExtractionTask:
    async def test_extraction_persists_assessments_and_deadlines(self, committed_doc):
        doc_id = await committed_doc.make_doc(make_pdf(["Midterm 30% due week 6", "Assignment 1"]))
        agent = FakeAgent()
        with patch("app.pipeline.courseops_task.get_agent", return_value=agent):
            result = await _process_document(doc_id)
        assert result["assessment_count"] == 1 and result["deadline_count"] == 1
        assert dict(agent.calls)["course_ops"] == {"type": "outline", "course": "OPSX1"}

        async with async_session_factory() as session:
            doc = await session.get(CourseDocument, doc_id)
            assert doc.status == "processed"
            assessments = (
                (
                    await session.execute(
                        select(Assessment).where(Assessment.course_id == committed_doc.course_id)
                    )
                )
                .scalars()
                .all()
            )
            assert [(a.title, a.weight_pct) for a in assessments] == [("Midterm", 30.0)]
            deadlines = (
                (
                    await session.execute(
                        select(Deadline).where(Deadline.course_id == committed_doc.course_id)
                    )
                )
                .scalars()
                .all()
            )
            assert [d.title for d in deadlines] == ["Assignment 1"]
            assert deadlines[0].is_confirmed is False  # AI-extracted deadlines await confirmation

    async def test_unextractable_document_is_marked_failed(self, committed_doc):
        doc_id = await committed_doc.make_doc(b"not a real pdf", name="bad.pdf")
        with patch("app.pipeline.courseops_task.get_agent", return_value=FakeAgent()):
            with pytest.raises(CourseOpsError):
                await _process_document(doc_id)
        async with async_session_factory() as session:
            doc = await session.get(CourseDocument, doc_id)
            assert doc.status == "failed"

    async def test_missing_document_raises(self):
        with pytest.raises(CourseOpsError):
            await _process_document("does-not-exist")
