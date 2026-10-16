"""Email notification service using aiosmtplib."""

import os
import re
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from html.parser import HTMLParser

import structlog
from jinja2 import Environment, FileSystemLoader

from app.config import settings

logger = structlog.get_logger()

# Template directory — resolve relative to this file
_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
_jinja_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)


_SKIP_TAGS = frozenset({"style", "script", "head", "title"})
_BLOCK_TAGS = frozenset(
    {"p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "table", "ul", "ol", "hr"}
)


class _TextExtractor(HTMLParser):
    """Collect readable text from HTML, keeping link targets as visible URLs."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0
        self._href: str | None = None
        self._link_text = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n")
        elif tag == "a":
            self._href = dict(attrs).get("href")
            self._link_text = ""

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n")
        elif tag == "a" and self._href:
            href = self._href
            # Show the URL unless the visible text already is the URL.
            if href.startswith(("http://", "https://")) and href not in self._link_text:
                self._chunks.append(f" {href} ")
            self._href = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self._chunks.append(data)
        if self._href is not None:
            self._link_text += data

    def text(self) -> str:
        raw = "".join(self._chunks)
        lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in raw.split("\n")]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"


def html_to_text(html_body: str) -> str:
    """Derive a readable text/plain body from HTML, keeping links as visible URLs.

    Args:
        html_body: HTML email body.

    Returns:
        Plain text with style/script content dropped and link targets inline.
    """
    parser = _TextExtractor()
    parser.feed(html_body)
    parser.close()
    return parser.text()


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
    kwargs.setdefault(
        "preferences_url", f"{settings.app_base_url.rstrip('/')}/settings/notifications"
    )
    return template.render(**kwargs)


async def send_email(
    to_email: str, subject: str, html_body: str, *, template: str = "inline"
) -> bool:
    """Send an email via SMTP. Best-effort: returns False on failure.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        html_body: HTML email body.
        template: Template name, the only identifier of the mail that is logged.
            The subject never is: it can carry a file name, course code or exam title.

    Returns:
        True if sent successfully, False otherwise.
    """
    if not _smtp_configured():
        logger.debug("email_skipped_no_smtp")
        return False

    try:
        import aiosmtplib

        msg = MIMEMultipart("alternative")
        msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=False)
        msg["Message-ID"] = make_msgid(domain=settings.smtp_from_email.rpartition("@")[2] or None)
        # RFC 2046: the last alternative is the preferred one, so plain goes first.
        msg.attach(MIMEText(html_to_text(html_body), "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html"))

        # aiosmtplib's `use_tls=True` means *implicit* TLS from the first byte
        # (SMTPS, conventionally port 465). Any other TLS-capable port — 587,
        # 25, ... — is a STARTTLS submission port: connect in plaintext, then
        # upgrade via `start_tls=True`. Passing use_tls=True on 587 fails with
        # "SSL: WRONG_VERSION_NUMBER" because the server isn't speaking TLS
        # from byte one. Infer the mechanism from the port so no new config
        # is needed and existing 465 deployments keep working unchanged.
        use_tls = settings.smtp_use_tls and settings.smtp_port == 465
        start_tls = settings.smtp_use_tls and settings.smtp_port != 465
        logger.debug(
            "email_smtp_tls_mode",
            port=settings.smtp_port,
            use_tls=use_tls,
            start_tls=start_tls,
        )

        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password.get_secret_value() or None,
            use_tls=use_tls,
            start_tls=start_tls,
        )

        logger.info("email_sent", template=template)
        return True

    except Exception as exc:
        hint = None
        # aiosmtplib wraps a handshake-time ssl.SSLError in SMTPConnectError,
        # so check __cause__ too — isinstance on exc alone misses it.
        if isinstance(exc, ssl.SSLError) or isinstance(exc.__cause__, ssl.SSLError):
            hint = (
                "TLS handshake failed — this usually means implicit TLS "
                "(use_tls) was attempted against a server expecting STARTTLS, "
                "or vice versa. Check smtp_port against smtp_use_tls."
            )
        logger.warning(
            "email_send_failed",
            template=template,
            hint=hint,
            exc_info=True,
        )
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
    return await send_email(to_email, subject, html_body, template=template_name)


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


async def send_password_reset(to_email: str, reset_url: str, expires_hours: int = 1) -> bool:
    """Send a password reset link.

    Args:
        to_email: Recipient email.
        reset_url: Fully-qualified link to the frontend reset page, token included.
        expires_hours: How long the link stays valid, for the copy.

    Returns:
        True if sent successfully.
    """
    return await send_templated_email(
        to_email=to_email,
        subject="StudyAIO: Reset your password",
        template_name="password_reset.html",
        reset_url=reset_url,
        expires_hours=expires_hours,
    )


async def send_email_verification(to_email: str, verify_url: str, expires_hours: int = 24) -> bool:
    """Send an email verification link.

    Args:
        to_email: Recipient email.
        verify_url: Fully-qualified link to the frontend verify page, token included.
        expires_hours: How long the link stays valid, for the copy.

    Returns:
        True if sent successfully.
    """
    return await send_templated_email(
        to_email=to_email,
        subject="StudyAIO: Verify your email",
        template_name="verify_email.html",
        verify_url=verify_url,
        expires_hours=expires_hours,
    )


async def send_invite(
    to_email: str,
    invite_url: str,
    expires_phrase: str,
    note: str | None = None,
) -> bool:
    """Send a beta invitation link.

    The URL carries a single-use token and is therefore a bearer credential —
    treat it like the password-reset link above. It is passed in fully formed so
    this layer never touches the token itself.

    Args:
        to_email: Recipient email.
        invite_url: Fully-qualified registration link, token included.
        expires_phrase: Human phrasing for the expiry, e.g. "in 14 days".
        note: Optional message from the admin who issued the invite.

    Returns:
        True if sent successfully.
    """
    return await send_templated_email(
        to_email=to_email,
        subject="You're invited to StudyAIO",
        template_name="invite.html",
        invite_url=invite_url,
        email=to_email,
        expires_phrase=expires_phrase,
        note=note,
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


async def send_study_nudge(to_email: str, body: str, cta_url: str) -> bool:
    """Send the day-2 "come back and study" nudge.

    Args:
        to_email: Recipient email.
        body: Plain-text message body.
        cta_url: Absolute link to the suggested next step.

    Returns:
        True if sent successfully.
    """
    return await send_templated_email(
        to_email=to_email,
        subject="StudyAIO: ready for your first study session?",
        template_name="study_nudge.html",
        body=body,
        cta_url=cta_url,
    )
