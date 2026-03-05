"""Email notification service using aiosmtplib."""

import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog
from jinja2 import Environment, FileSystemLoader

from app.config import settings

logger = structlog.get_logger()

# Template directory — resolve relative to this file
_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
_jinja_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)


def _smtp_configured() -> bool:
    """Check if SMTP credentials are configured."""
    return bool(settings.smtp_host and settings.smtp_from_email)


def render_template(template_name: str, **kwargs: object) -> str:
    """Render an HTML email template.

    Args:
        template_name: Template filename (e.g. 'pipeline_complete.html').
        **kwargs: Template variables.

    Returns:
        Rendered HTML string.
    """
    template = _jinja_env.get_template(template_name)
    return template.render(**kwargs)


async def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send an email via SMTP. Best-effort: returns False on failure.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        html_body: HTML email body.

    Returns:
        True if sent successfully, False otherwise.
    """
    if not _smtp_configured():
        logger.debug("email_skipped_no_smtp", to=to_email)
        return False

    try:
        import aiosmtplib

        msg = MIMEMultipart("alternative")
        msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))

        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password.get_secret_value() or None,
            use_tls=settings.smtp_use_tls,
        )

        logger.info("email_sent", to=to_email, subject=subject)
        return True

    except Exception:
        logger.warning("email_send_failed", to=to_email, subject=subject, exc_info=True)
        return False


async def send_templated_email(
    to_email: str, subject: str, template_name: str, **kwargs: object
) -> bool:
    """Render a template and send it as an email.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        template_name: Template filename.
        **kwargs: Template variables.

    Returns:
        True if sent successfully, False otherwise.
    """
    html_body = render_template(template_name, **kwargs)
    return await send_email(to_email, subject, html_body)


async def send_pipeline_complete(
    to_email: str,
    filename: str,
    course_code: str,
    week: int,
    flashcard_count: int,
    quiz_count: int,
) -> bool:
    """Send pipeline completion notification email.

    Args:
        to_email: Recipient email.
        filename: Processed file name.
        course_code: Course code.
        week: Week number.
        flashcard_count: Number of flashcards generated.
        quiz_count: Number of quiz questions generated.

    Returns:
        True if sent successfully.
    """
    return await send_templated_email(
        to_email=to_email,
        subject=f"StudyAIO: {filename} processed for {course_code}",
        template_name="pipeline_complete.html",
        filename=filename,
        course_code=course_code,
        week=week,
        flashcard_count=flashcard_count,
        quiz_count=quiz_count,
    )


async def send_exam_reminder(
    to_email: str, exam_title: str, course_code: str, exam_date: str
) -> bool:
    """Send exam reminder notification email.

    Args:
        to_email: Recipient email.
        exam_title: Exam title.
        course_code: Course code.
        exam_date: Formatted exam date string.

    Returns:
        True if sent successfully.
    """
    return await send_templated_email(
        to_email=to_email,
        subject=f"StudyAIO: Exam reminder — {exam_title}",
        template_name="exam_reminder.html",
        exam_title=exam_title,
        course_code=course_code,
        exam_date=exam_date,
    )


async def send_cards_due(to_email: str, due_count: int) -> bool:
    """Send due flashcards reminder email.

    Args:
        to_email: Recipient email.
        due_count: Number of flashcards due.

    Returns:
        True if sent successfully.
    """
    return await send_templated_email(
        to_email=to_email,
        subject=f"StudyAIO: {due_count} flashcards due today",
        template_name="cards_due.html",
        due_count=due_count,
    )


async def send_weekly_digest(
    to_email: str,
    cards_reviewed: int,
    quiz_attempts: int,
    study_sessions: int,
    streak_days: int,
    due_count: int,
) -> bool:
    """Send weekly study digest email.

    Args:
        to_email: Recipient email.
        cards_reviewed: Cards reviewed this week.
        quiz_attempts: Quiz attempts this week.
        study_sessions: Study sessions this week.
        streak_days: Current study streak.
        due_count: Cards currently due.

    Returns:
        True if sent successfully.
    """
    return await send_templated_email(
        to_email=to_email,
        subject="StudyAIO: Your weekly study digest",
        template_name="weekly_digest.html",
        cards_reviewed=cards_reviewed,
        quiz_attempts=quiz_attempts,
        study_sessions=study_sessions,
        streak_days=streak_days,
        due_count=due_count,
    )
