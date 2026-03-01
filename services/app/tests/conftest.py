"""Shared test fixtures for StudyAIO."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.agents.base import (
    ClassificationResult,
    SummaryResult,
)

# ── Sample data dicts ──────────────────────────────────────────────


@pytest.fixture
def sample_course_data():
    """Minimal course data dict."""
    return {
        "id": "course-001",
        "code": "CSIT302",
        "name": "Cybersecurity",
    }


@pytest.fixture
def sample_artifact_data():
    """Minimal artifact data dict."""
    return {
        "id": "artifact-001",
        "course_id": "course-001",
        "week": 5,
        "title": "Network Security",
        "original_filename": "CSIT302_Week5.pdf",
        "file_path": "/app/data/uploads/artifact-001_CSIT302_Week5.pdf",
        "file_type": "pdf",
        "sha256": "a" * 64,
        "file_size_bytes": 1024,
        "status": "ingested",
    }


@pytest.fixture
def sample_manifest():
    """Sample extraction manifest dict."""
    return {
        "pages": [
            {
                "page_number": 1,
                "text": "Introduction to Network Security\nCSIT302 Week 5",
                "images": [{"filename": "page1_img1.png", "caption": "", "position": "page_1"}],
            },
            {
                "page_number": 2,
                "text": "Firewall types and configurations\nPacket filtering vs stateful inspection",
                "images": [],
            },
        ],
        "metadata": {"extractor_version": "1.0", "source_type": "pdf"},
    }


# ── Mock agent ──────────────────────────────────────────────────────


@pytest.fixture
def mock_agent():
    """AsyncMock of AgentAdapter with sensible return values."""
    agent = AsyncMock()
    agent.classify_lecture.return_value = ClassificationResult(
        course_code="CSIT302",
        week=5,
        title="Network Security",
        confidence=0.92,
        reasoning="Course code in header, week in filename",
    )
    agent.generate_summary.return_value = SummaryResult(
        content_md="# CSIT302 — Week 5: Network Security\n\n## Key Concepts\n- Firewalls",
        embedded_images=[],
    )
    return agent


# ── Mock DB session ─────────────────────────────────────────────────


@pytest.fixture
def mock_session():
    """AsyncMock of AsyncSession with basic query support."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


# ── Async HTTP test client ────────────────────────────────────────


@pytest.fixture
async def async_client(mock_session):
    """Async HTTP client for testing FastAPI endpoints."""
    from app.core.database import get_session
    from app.main import app

    async def override():
        yield mock_session

    app.dependency_overrides[get_session] = override
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()


# ── Programmatic fixture file creators ──────────────────────────────


@pytest.fixture
def simple_pdf(tmp_path):
    """Create a minimal PDF file using PyMuPDF."""
    import fitz

    pdf_path = tmp_path / "test_lecture.pdf"
    doc = fitz.open()

    # Page 1
    page1 = doc.new_page(width=595, height=842)
    page1.insert_text((72, 72), "CSIT302 Week 5\nNetwork Security Fundamentals", fontsize=14)

    # Page 2
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text(
        (72, 72), "Firewalls are network security systems\nthat monitor traffic.", fontsize=12
    )

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def simple_docx(tmp_path):
    """Create a minimal DOCX file using python-docx."""
    import docx

    docx_path = tmp_path / "test_lecture.docx"
    document = docx.Document()

    document.add_heading("CSIT302 Week 5: Network Security", level=1)
    document.add_paragraph("This lecture covers network security fundamentals.")
    document.add_heading("Firewalls", level=2)
    document.add_paragraph(
        "A firewall monitors and controls incoming and outgoing network traffic."
    )

    document.save(str(docx_path))
    return docx_path


@pytest.fixture
def simple_pptx(tmp_path):
    """Create a minimal PPTX file using python-pptx."""
    from pptx import Presentation

    pptx_path = tmp_path / "test_lecture.pptx"
    prs = Presentation()

    # Slide 1 — title
    slide1 = prs.slides.add_slide(prs.slide_layouts[0])
    slide1.shapes.title.text = "CSIT302 Week 5"
    slide1.placeholders[1].text = "Network Security Fundamentals"

    # Slide 2 — content
    slide2 = prs.slides.add_slide(prs.slide_layouts[1])
    slide2.shapes.title.text = "Firewalls"
    slide2.placeholders[1].text = "Packet filtering\nStateful inspection\nApplication layer"

    # Slide 3 — with speaker notes
    slide3 = prs.slides.add_slide(prs.slide_layouts[1])
    slide3.shapes.title.text = "IDS/IPS"
    slide3.placeholders[1].text = "Intrusion Detection and Prevention Systems"
    notes_slide = slide3.notes_slide
    notes_slide.notes_text_frame.text = "Important: Explain difference between IDS and IPS"

    prs.save(str(pptx_path))
    return pptx_path
