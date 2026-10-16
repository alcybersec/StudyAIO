"""Floors 1 and 2 — the Telegram webhook is authenticated, and its secrets stay secret.

M34-S2-SEC-015 (R-052). ``POST /api/notifications/telegram/webhook`` takes no
user session: Telegram calls it. Before SEC-015 its "secret" header was compared
with ``!=`` against ``TELEGRAM_WEBHOOK_URL`` itself, a URL derivable from the
public host (and the link endpoint even returns its last path segment as the bot
username), and an unset URL accepted every caller. Since SEC-015 the header is
checked in constant time against a dedicated ``TELEGRAM_WEBHOOK_SECRET``
(``SecretStr``), registered with Telegram by ``python -m app.cli
register-telegram-webhook``. Review: ``docs/gates/M34/sec015-safety.md``.

What an authenticated update can do (floor 1): ``handle_telegram_webhook`` acts
only on ``/start <code>``, which binds the sending chat to the one
``telegram_links`` row whose digest matches the code. So a forged update could
pair an attacker's chat with an account only by also holding that account's
pending pairing code; the secret is the second lock on that door, and it must
hold before any statement runs.

Pins:

* the header is compared with ``hmac.compare_digest`` and with no ``==``/``!=``;
* every forgery (no header, empty, wrong, a prefix or extension of the secret,
  the webhook URL, the bot token) is a 403 of one shape, and a forged ``/start``
  carrying a valid pairing code runs no statement and pairs nothing; the
  correct secret pairs only the row the code names (control);
* with the secret unset a multi-user instance (``SELF_HOSTED`` included) rejects
  every call, the URL too, and warns once, valuelessly;
* ``SINGLE_USER_MODE`` with the secret unset accepts (ruled acceptable here: the
  instance has one tenant and anyone who reaches it is already its admin), and a
  set secret is still enforced there;
* neither the secret nor the bot token is logged by the webhook, returned by any
  response, or printed by the CLI on success, rejection or network failure; the
  send path logs no bot token on a network failure;
* ``register_webhook`` is called only from the CLI, which logs at ``WARNING``.

Finding F1 (strict ``xfail``, not blocking): at ``INFO`` httpx's own request log
prints the ``setWebhook`` URL, which carries the bot token. Unreachable while the
CLI is the only caller (pinned); RED until ``configure_logging`` caps the
``httpx``/``httpcore`` loggers at ``WARNING``.
"""

from __future__ import annotations

import ast
import hashlib
import subprocess
import sys
import textwrap
from unittest.mock import patch

import pytest
from pydantic import SecretStr

URL = "/api/notifications/telegram/webhook"
HEADER = "x-telegram-bot-api-secret-token"
SECRET = "floor2-TG-webhook-secret_0123456789abcdef"
BOT_TOKEN = "987654321:FLOOR2-bot-token-AAbbCCddEEff0123456789"
WEBHOOK_URL = "https://studyaio.example.com/api/notifications/telegram/webhook"
CODE_B = "floor2-pairing-code-of-user-b"


def _digest(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _db():
    """A linked to chat 111; B pending with ``CODE_B`` (stored as its digest)."""
    from app.models.telegram_link import TelegramLink
    from tests.safety._minidb import MiniDB

    db = MiniDB()
    db.add(
        TelegramLink(id="tl-a", user_id="floor-tg-a", link_token=None, verified=True, chat_id=111)
    )
    db.add(
        TelegramLink(id="tl-b", user_id="floor-tg-b", link_token=_digest(CODE_B), verified=False)
    )
    return db


class _RecSession:
    """MiniSession that records every statement and answers commit/rollback."""

    def __init__(self, db) -> None:
        from tests.safety._minidb import MiniSession

        self._inner = MiniSession(db)
        self.statements: list = []
        self.commits = 0

    async def execute(self, statement, *a, **k):
        self.statements.append(statement)
        return await self._inner.execute(statement, *a, **k)

    def add(self, obj, *a, **k) -> None:
        self.statements.append(("add", obj))
        self._inner.add(obj)

    async def delete(self, obj) -> None:
        self.statements.append(("delete", obj))
        await self._inner.delete(obj)

    async def flush(self, *a, **k) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None


def _state(db) -> list[tuple]:
    return sorted(
        (o.user_id, o.verified, o.chat_id, o.username, o.link_token)
        for o in db.rows["telegram_links"]
    )


def _start(code: str, chat_id: int = 666) -> dict:
    return {
        "message": {"text": f"/start {code}", "chat": {"id": chat_id}, "from": {"username": "x"}}
    }


@pytest.fixture
def settings_for():
    """Patch the webhook-relevant settings for one scenario."""
    from contextlib import ExitStack

    from app.config import settings

    stack = ExitStack()

    def apply(*, secret: str, single_user: bool = False, self_hosted: bool = False) -> None:
        stack.enter_context(patch.object(settings, "telegram_webhook_secret", SecretStr(secret)))
        stack.enter_context(patch.object(settings, "telegram_bot_token", SecretStr(BOT_TOKEN)))
        stack.enter_context(patch.object(settings, "telegram_webhook_url", WEBHOOK_URL))
        stack.enter_context(patch.object(settings, "single_user_mode", single_user))
        stack.enter_context(patch.object(settings, "self_hosted", self_hosted or single_user))

    yield apply
    stack.close()


@pytest.fixture(autouse=True)
def _reset_warned():
    from app.api import notifications

    notifications._unset_secret_warned = False
    yield
    notifications._unset_secret_warned = False


@pytest.fixture
def log_stream():
    """The app's real logging configuration at DEBUG on a fresh root handler; restored after."""
    import io
    import logging

    import structlog

    from app.core.logging import configure_logging

    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    saved_config = structlog.get_config()
    out = io.StringIO()
    root.handlers = [logging.StreamHandler(out)]
    try:
        configure_logging("DEBUG")
        root.setLevel(logging.DEBUG)
        yield out
    finally:
        root.handlers = saved_handlers
        root.setLevel(saved_level)
        structlog.configure(**saved_config)


async def _post(db, headers: dict, body: dict):
    """Call the real route with the real handler over MiniDB; returns (response, session)."""
    import httpx

    from app.core.database import get_session
    from app.main import app

    session = _RecSession(db)

    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(URL, json=body, headers=headers)
    finally:
        app.dependency_overrides.pop(get_session, None)
    return response, session


# ── constant-time comparison ──────────────────────────────────────────────


def _webhook_fn() -> ast.AsyncFunctionDef:
    from tests.safety._source import APP_ROOT, parse

    tree = parse(APP_ROOT / "api" / "notifications.py")
    [fn] = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "telegram_webhook"
    ]
    return fn


def test_floor2_webhook_secret_is_compared_only_with_compare_digest():
    fn = _webhook_fn()
    compares = [
        n
        for n in ast.walk(fn)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "compare_digest"
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id in {"hmac", "secrets"}
    ]
    assert len(compares) == 1, "telegram_webhook must call hmac.compare_digest exactly once"

    # Names bound from the header or the setting, then: no ==/!= on any of them.
    tainted: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            src = ast.unparse(node.value)
            if "telegram_webhook_secret" in src or "headers" in src:
                tainted |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    assert len(tainted) >= 2, f"cannot find the header and secret locals (vacuous): {tainted}"
    offences = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Compare) and any(
            isinstance(op, ast.Eq | ast.NotEq | ast.In | ast.NotIn) for op in node.ops
        ):
            names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            if (
                names & tainted
                or "telegram_webhook" in ast.unparse(node)
                or "headers" in (ast.unparse(node))
            ):
                offences.append(f"line {node.lineno}: {ast.unparse(node)}")
    assert not offences, "secret compared with a short-circuiting operator:\n" + "\n".join(offences)
    assert "telegram_webhook_url" not in ast.unparse(fn), "the webhook URL is back in the check"


@pytest.mark.asyncio
async def test_floor2_webhook_compare_digest_sees_the_header_and_the_secret(settings_for):
    import hmac

    settings_for(secret=SECRET)
    db = _db()
    with patch("app.api.notifications.hmac.compare_digest", wraps=hmac.compare_digest) as spy:
        response, _ = await _post(db, {HEADER: "floor2-presented"}, _start(CODE_B))
    assert response.status_code == 403
    spy.assert_called_once()
    args = {bytes(a) if isinstance(a, bytes | bytearray) else a for a in spy.call_args.args}
    assert args == {b"floor2-presented", SECRET.encode()}, spy.call_args


# ── forgeries are rejected before anything runs ───────────────────────────

FORGERIES = {
    "no-header": None,
    "empty": "",
    "wrong": "floor2-wrong-secret",
    "prefix": SECRET[:-1],
    "extended": SECRET + "x",
    "case": SECRET.upper(),
    "webhook-url": WEBHOOK_URL,
    "url-last-segment": WEBHOOK_URL.split("/")[-1],
    "bot-token": BOT_TOKEN,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("which", list(FORGERIES))
async def test_floor1_forged_update_with_a_valid_pairing_code_pairs_nothing(
    settings_for, log_stream, which
):
    settings_for(secret=SECRET)
    db = _db()
    before = _state(db)
    presented = FORGERIES[which]
    headers = {} if presented is None else {HEADER: presented}
    response, session = await _post(db, headers, _start(CODE_B))
    assert response.status_code == 403, which
    assert response.json() == {"detail": "Invalid webhook secret"}, which
    assert session.statements == [] and session.commits == 0, (which, session.statements)
    assert _state(db) == before, which
    text = log_stream.getvalue()
    for value in (SECRET, BOT_TOKEN, CODE_B, _digest(CODE_B)):
        assert value not in text, f"{which}: a secret reached the log"


@pytest.mark.asyncio
async def test_floor1_correct_secret_pairs_only_the_row_the_code_names(settings_for, log_stream):
    """Control for the forgery pins, and the limit of what an authentic update can do."""
    settings_for(secret=SECRET)
    db = _db()
    response, session = await _post(db, {HEADER: SECRET}, _start(CODE_B, chat_id=111))
    assert response.status_code == 200, response.text
    body = response.text
    for value in (SECRET, BOT_TOKEN, WEBHOOK_URL):
        assert value not in body, "the webhook response carries a secret"
    # B is paired with the sending chat; A's verified link is untouched even though
    # the update came from A's chat; nothing was deleted or inserted.
    assert _state(db) == sorted(
        [("floor-tg-a", True, 111, None, None), ("floor-tg-b", True, 111, "x", None)]
    )
    assert all(not isinstance(s, tuple) for s in session.statements), session.statements
    tables = {t.name for s in session.statements for t in s.get_final_froms()}
    assert tables == {"telegram_links"}, tables

    # A second authentic update with an unknown code mutates nothing.
    before = _state(db)
    response, _ = await _post(db, {HEADER: SECRET}, _start("floor2-no-such-code"))
    assert response.status_code == 200 and _state(db) == before
    text = log_stream.getvalue()
    for value in (SECRET, BOT_TOKEN, CODE_B):
        assert value not in text


# ── secret unset ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("self_hosted", [False, True], ids=["cloud", "self-hosted"])
async def test_floor1_unset_secret_on_a_multi_user_instance_rejects_everything(
    settings_for, log_stream, self_hosted
):
    settings_for(secret="", self_hosted=self_hosted)
    db = _db()
    before = _state(db)
    # The first call carries a value, so a warning that logged it would show it.
    for headers in ({HEADER: "floor2-anything"}, {}, {HEADER: ""}, {HEADER: WEBHOOK_URL}):
        response, session = await _post(db, headers, _start(CODE_B))
        assert response.status_code == 403, headers
        assert response.json() == {"detail": "Invalid webhook secret"}
        assert session.statements == [] and session.commits == 0
    assert _state(db) == before
    text = log_stream.getvalue()
    assert text.count("telegram_webhook_secret_unset_rejecting_all") == 1, text
    for value in ("floor2-anything", WEBHOOK_URL, BOT_TOKEN, CODE_B):
        assert value not in text


@pytest.mark.asyncio
async def test_floor1_single_user_unset_secret_accepts_by_ruling(settings_for):
    """SEC-015 ruling: one tenant, and anyone who reaches a single-user API is its admin."""
    settings_for(secret="", single_user=True)
    db = _db()
    response, _ = await _post(db, {}, _start(CODE_B))
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_floor1_single_user_still_enforces_a_set_secret(settings_for):
    settings_for(secret=SECRET, single_user=True)
    db = _db()
    before = _state(db)
    for headers in ({}, {HEADER: "floor2-wrong"}):
        response, session = await _post(db, headers, _start(CODE_B))
        assert response.status_code == 403
        assert session.statements == []
    assert _state(db) == before
    response, _ = await _post(db, {HEADER: SECRET}, _start(CODE_B))
    assert response.status_code == 200


# ── the secret and the bot token never leave the process ──────────────────


def test_floor2_webhook_secret_and_bot_token_reach_no_response_or_log_call():
    """Static: outside config, the two settings are read only where they are used."""
    from tests.safety._source import APP_ROOT, app_modules, parse, rel, walk_with_scope

    allowed = {
        "telegram_webhook_secret": {
            ("app/api/notifications.py", "telegram_webhook"),
            ("app/services/telegram_service.py", "register_webhook"),
        },
        "telegram_bot_token": {
            ("app/api/notifications.py", "generate_telegram_link"),  # presence check only
            ("app/services/telegram_service.py", "_telegram_configured"),
            ("app/services/telegram_service.py", "register_webhook"),
            ("app/services/telegram_service.py", "send_telegram_message"),
        },
    }
    found: dict[str, set] = {k: set() for k in allowed}
    for path in app_modules(exclude=("app/config.py",)):
        for node, scope in walk_with_scope(parse(path)):
            if isinstance(node, ast.Attribute) and node.attr in allowed:
                found[node.attr].add((rel(path), scope))
    for name, sites in found.items():
        assert sites <= allowed[name], f"{name} read at an unreviewed site: {sites - allowed[name]}"
        assert sites, f"{name}: no reads found (vacuous)"

    # The link endpoint uses the bot token only as a truthiness check.
    fn = next(
        n
        for n in ast.walk(parse(APP_ROOT / "api" / "notifications.py"))
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "generate_telegram_link"
    )
    uses = [n for n in ast.walk(fn) if isinstance(n, ast.Name) and n.id == "bot_token"]
    assert len(uses) == 2, "bot_token used beyond `bot_token = ...; if not bot_token`"


def test_floor2_register_webhook_is_called_only_from_the_cli_at_warning():
    from tests.safety._source import APP_ROOT, app_modules, parse, rel, walk_with_scope

    callers = set()
    for path in app_modules():
        for node, scope in walk_with_scope(parse(path)):
            if (
                isinstance(node, ast.Attribute | ast.Name)
                and (
                    getattr(node, "attr", None) == "register_webhook"
                    or getattr(node, "id", None) == "register_webhook"
                )
            ) or (
                isinstance(node, ast.ImportFrom)
                and any(a.name == "register_webhook" for a in node.names)
            ):
                callers.add((rel(path), scope))
    assert callers == {("app/cli.py", "_register_telegram_webhook")}, callers

    main = next(
        n
        for n in ast.walk(parse(APP_ROOT / "cli.py"))
        if isinstance(n, ast.FunctionDef) and n.name == "main"
    )
    first = [
        n
        for n in ast.walk(main)
        if isinstance(n, ast.Call) and ast.unparse(n.func) == "configure_logging"
    ]
    assert [ast.unparse(c) for c in first] == ["configure_logging('WARNING')"], (
        "the CLI must log at WARNING: httpx's INFO request line carries the bot token (F1)"
    )


_CLI_SCRIPT = textwrap.dedent(
    """
    import sys
    from unittest.mock import patch

    import httpx
    from pydantic import SecretStr

    from app import cli
    from app.config import settings

    mode, token, secret, url = sys.argv[1:5]
    real = httpx.AsyncClient

    def handler(request):
        if mode == "connect-error":
            raise httpx.ConnectError(f"cannot reach {request.url}", request=request)
        if mode == "timeout":
            raise httpx.ReadTimeout(f"timed out on {request.url}", request=request)
        if mode == "rejected":
            return httpx.Response(401, json={"ok": False, "description": f"bad {request.url}"})
        if mode == "not-json":
            return httpx.Response(502, text=f"<html>{request.url}</html>")
        return httpx.Response(200, json={"ok": True})

    def client(**kw):
        return real(transport=httpx.MockTransport(handler), **kw)

    with (
        patch.object(settings, "telegram_bot_token", SecretStr(token)),
        patch.object(settings, "telegram_webhook_secret", SecretStr(secret)),
        patch.object(settings, "telegram_webhook_url", url),
        patch("app.services.telegram_service.httpx.AsyncClient", side_effect=client),
    ):
        sys.exit(cli.main(["register-telegram-webhook"]))
    """
)


@pytest.mark.parametrize(
    ("mode", "code"),
    [("ok", 0), ("connect-error", 1), ("timeout", 1), ("rejected", 1), ("not-json", 1)],
)
def test_floor2_cli_prints_no_bot_token_or_secret(mode, code):
    """A fresh process, so the CLI's own logging configuration is the one in force."""
    from tests.safety._source import SERVICE_ROOT

    proc = subprocess.run(
        [sys.executable, "-c", _CLI_SCRIPT, mode, BOT_TOKEN, SECRET, WEBHOOK_URL],
        cwd=SERVICE_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        env={**__import__("os").environ, "PYTHONPATH": str(SERVICE_ROOT)},
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == code, output
    assert output.strip(), "the CLI printed nothing (vacuous)"
    for value in (BOT_TOKEN, BOT_TOKEN.split(":")[1], SECRET):
        assert value not in output, f"{mode}: a secret reached the CLI output:\n{output}"


@pytest.mark.asyncio
async def test_floor2_send_path_logs_no_bot_token_on_network_failure(log_stream):
    """``send_telegram_message`` logs ``exc_info``; a refused connection must not carry the token."""
    import aiogram
    from aiogram.client.session.aiohttp import AiohttpSession
    from aiogram.client.telegram import TelegramAPIServer

    from app.config import settings
    from app.services import telegram_service

    real_bot = aiogram.Bot
    closed = TelegramAPIServer.from_base("http://127.0.0.1:9")

    def bot(token, **kw):
        return real_bot(token=token, session=AiohttpSession(api=closed))

    with (
        patch.object(settings, "telegram_bot_token", SecretStr(BOT_TOKEN)),
        patch.object(aiogram, "Bot", side_effect=bot),
    ):
        assert await telegram_service.send_telegram_message(4242, "hello") is False
    text = log_stream.getvalue()
    assert "telegram_send_failed" in text and "Traceback" in text, text
    for value in (BOT_TOKEN, BOT_TOKEN.split(":")[1]):
        assert value not in text, "the bot token reached the log on a send failure"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "F1 (SEC-015): httpx logs `HTTP Request: POST https://api.telegram.org/bot<token>/"
        "setWebhook` at INFO. Unreachable while only the CLI (WARNING) calls register_webhook; "
        "RED until configure_logging caps the httpx/httpcore loggers at WARNING."
    ),
)
@pytest.mark.asyncio
async def test_floor2_register_webhook_logs_no_bot_token_at_info(log_stream):
    import httpx

    from app.config import settings
    from app.services import telegram_service

    real = httpx.AsyncClient

    def client(**kw):
        return real(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"ok": True})), **kw
        )

    with (
        patch.object(settings, "telegram_bot_token", SecretStr(BOT_TOKEN)),
        patch.object(settings, "telegram_webhook_secret", SecretStr(SECRET)),
        patch.object(settings, "telegram_webhook_url", WEBHOOK_URL),
        patch("app.services.telegram_service.httpx.AsyncClient", side_effect=client),
    ):
        assert await telegram_service.register_webhook() is True
    text = log_stream.getvalue()
    assert "telegram_webhook_registered" in text, text
    for value in (BOT_TOKEN, SECRET):
        assert value not in text
