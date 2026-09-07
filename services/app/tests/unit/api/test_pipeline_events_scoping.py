"""Cross-tenant scoping of the pipeline-events SSE stream (issue #69).

`GET /api/uploads/pipeline-events` used to subscribe to one instance-wide
Redis channel (`pipeline:events`) and filter only on a caller-supplied
`artifact_id`. The resolved `user` was never referenced, so any authenticated
caller got a live feed of every upload on the instance, and passing someone
else's `artifact_id` turned it into a targeted watch.

Neither existing guard could catch it: the endpoint *is* authenticated
(`test_endpoint_authn_guard`) and performs no id-addressed object lookup to
scope (`test_endpoint_scoping_guard`). The leak was the pub/sub fan-out.

## Why the fake broker here is channel-aware

`tests/unit/conftest.py`'s autouse `FakeRedis` deliberately yields nothing from
pub/sub, which is right for tests that merely must not open a socket but makes
a scoping test vacuous. `_Broker` below keys messages by channel and hands a
subscriber only what was published to a channel it subscribed to — the one
property the fix depends on. Publishing goes through the real
`publish_pipeline_event`, so these tests cover the publisher's channel choice
and the subscriber's channel choice together.
"""

import ast
import inspect
import json
import pathlib
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.api import uploads
from app.core.auth import ACCESS_TOKEN_COOKIE, create_access_token
from app.services import event_service, user_service

OWNER_ID = "11111111-1111-1111-1111-111111111111"
OTHER_ID = "22222222-2222-2222-2222-222222222222"

APP_DIR = pathlib.Path(uploads.__file__).resolve().parents[1]


class _Broker:
    """In-memory pub/sub that respects channels."""

    def __init__(self) -> None:
        self.queues: dict[str, list[str]] = {}

    def push(self, channel: str, payload: str) -> None:
        self.queues.setdefault(channel, []).append(payload)


class _FakePubSub:
    def __init__(self, broker: _Broker) -> None:
        self._broker = broker
        self.channels: set[str] = set()

    async def subscribe(self, *channels: str) -> None:
        self.channels.update(channels)

    async def unsubscribe(self, *channels: str) -> None:
        self.channels.difference_update(channels)

    async def get_message(self, ignore_subscribe_messages: bool = True, timeout: float = 0.0):
        for channel in sorted(self.channels):
            queue = self._broker.queues.get(channel)
            if queue:
                return {"type": "message", "channel": channel, "data": queue.pop(0)}
        return None

    async def aclose(self) -> None:
        return None


class _FakeRedis:
    """`Redis`-shaped stand-in bound to one `_Broker`."""

    broker: _Broker

    def __init__(self) -> None:
        pass

    @classmethod
    def from_url(cls, *args, **kwargs) -> "_FakeRedis":
        return cls()

    async def publish(self, channel: str, message: str) -> int:
        self.broker.push(channel, message)
        return 1

    def pubsub(self) -> _FakePubSub:
        return _FakePubSub(self.broker)

    async def aclose(self) -> None:
        return None


class _FakeRequest:
    """Request stand-in that disconnects after a fixed number of loop passes."""

    def __init__(self, disconnect_after: int = 1, cookies: dict[str, str] | None = None) -> None:
        self.cookies = cookies or {}
        self._passes = 0
        self._disconnect_after = disconnect_after

    async def is_disconnected(self) -> bool:
        self._passes += 1
        return self._passes > self._disconnect_after


@pytest.fixture
def broker(monkeypatch):
    """Channel-aware broker wired into both the publisher and the subscriber."""
    shared = _Broker()

    class Bound(_FakeRedis):
        broker = shared

    # The autouse `fake_redis` fixture has already patched both modules; these
    # override it with a broker that routes by channel.
    monkeypatch.setattr(uploads, "Redis", Bound)
    monkeypatch.setattr(event_service, "Redis", Bound)
    return shared


async def _drain(stream) -> list[dict]:
    """Collect the `pipeline` event payloads a stream yields."""
    payloads = []
    async for chunk in stream:
        if chunk.get("event") == "pipeline":
            payloads.append(json.loads(chunk["data"]))
    return payloads


@pytest.mark.asyncio
class TestPipelineEventScoping:
    """The stream must never carry another user's events."""

    async def test_no_artifact_id_yields_only_the_callers_own_events(self, broker, make_user):
        """With no filter at all, the caller sees their events and nobody else's.

        This is the exact exploit from #69: open the stream with no query
        parameter and read the whole instance.
        """
        owner = make_user(id=OWNER_ID, email="owner@example.com", username="owner")

        await event_service.publish_pipeline_event(
            "art-owner", "classify", "completed", user_id=OWNER_ID
        )
        await event_service.publish_pipeline_event(
            "art-other", "classify", "completed", user_id=OTHER_ID
        )

        request = _FakeRequest(disconnect_after=2)
        payloads = await _drain(uploads.pipeline_event_stream(request, "", owner))

        assert [p["artifact_id"] for p in payloads] == ["art-owner"], (
            "stream carried an artifact belonging to another user"
        )

    async def test_another_users_artifact_id_yields_nothing(self, broker, make_user):
        """Naming someone else's artifact is a targeted watch — it must be empty.

        The old code filtered *only* on this parameter, so supplying it was the
        whole attack rather than a restriction.
        """
        owner = make_user(id=OWNER_ID, email="owner@example.com", username="owner")

        await event_service.publish_pipeline_event(
            "art-other", "summarize", "failed", user_id=OTHER_ID
        )

        request = _FakeRequest(disconnect_after=1)
        payloads = await _drain(uploads.pipeline_event_stream(request, "art-other", owner))

        assert payloads == [], "stream let a caller watch another user's artifact by id"

    async def test_owner_still_receives_their_own_filtered_events(self, broker, make_user):
        """Positive control: the feature still works for the artifact's owner."""
        owner = make_user(id=OWNER_ID, email="owner@example.com", username="owner")

        await event_service.publish_pipeline_event(
            "art-owner", "index", "started", message="indexing", user_id=OWNER_ID
        )

        request = _FakeRequest(disconnect_after=1)
        payloads = await _drain(uploads.pipeline_event_stream(request, "art-owner", owner))

        assert payloads == [
            {
                "artifact_id": "art-owner",
                "stage": "index",
                "status": "started",
                "message": "indexing",
            }
        ], "the documented wire format changed, or the owner stopped receiving events"

    async def test_mis_addressed_event_on_the_callers_channel_is_dropped(self, broker, make_user):
        """Second lock: a payload whose owner is someone else is not forwarded.

        Unreachable through `publish_pipeline_event`, which derives the channel
        from the same `user_id` it stamps on the payload. It is reachable if a
        future publisher builds a channel name by hand.
        """
        owner = make_user(id=OWNER_ID, email="owner@example.com", username="owner")

        broker.push(
            event_service.pipeline_events_channel(OWNER_ID),
            json.dumps(
                {
                    "artifact_id": "art-other",
                    "stage": "extract",
                    "status": "failed",
                    "message": None,
                    "user_id": OTHER_ID,
                }
            ),
        )

        request = _FakeRequest(disconnect_after=1)
        payloads = await _drain(uploads.pipeline_event_stream(request, "", owner))

        assert payloads == [], "an event stamped with another user's id was forwarded"


@pytest.mark.asyncio
class TestPipelineEventPublisherChannels:
    """Every event lands on its owner's channel, or on no channel at all."""

    async def test_event_is_published_to_the_owners_channel(self, broker):
        """The channel name is derived from the owner, not shared."""
        await event_service.publish_pipeline_event(
            "art-owner", "assets", "completed", user_id=OWNER_ID
        )

        assert list(broker.queues) == [f"pipeline:events:{OWNER_ID}"]
        assert "pipeline:events" not in broker.queues, "an instance-wide channel is back"

    async def test_event_without_an_owner_is_dropped_not_broadcast(self, broker):
        """No owner means no safe recipient, so nothing is published."""
        await event_service.publish_pipeline_event("art-orphan", "ingest", "failed", user_id=None)

        assert broker.queues == {}, "an unowned event was published to some channel"


class TestEveryPublisherSuppliesTheOwner:
    """Per-user channels only hold if no publisher can skip the owner."""

    @pytest.mark.parametrize(
        "publisher",
        [event_service.publish_pipeline_event, event_service.publish_pipeline_event_sync],
    )
    def test_user_id_is_required_and_keyword_only(self, publisher):
        """A call site that forgets the owner must fail, not broadcast."""
        param = inspect.signature(publisher).parameters["user_id"]

        assert param.kind is inspect.Parameter.KEYWORD_ONLY, (
            "user_id must be keyword-only so it cannot be confused with `message`"
        )
        assert param.default is inspect.Parameter.empty, (
            "user_id has a default, so a publisher can silently omit the owner"
        )

    def test_no_call_site_omits_the_owner(self):
        """Belt to the signature's braces, and a better error message than TypeError."""
        offenders = []
        for path in sorted(APP_DIR.rglob("*.py")):
            source = path.read_text()
            for node in ast.walk(ast.parse(source)):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                if not name.startswith("publish_pipeline_event"):
                    continue
                if not any(kw.arg == "user_id" for kw in node.keywords):
                    offenders.append(f"{path.relative_to(APP_DIR)}:{node.lineno}")

        assert not offenders, (
            f"pipeline event published without an owner, so it has no channel to go to: {offenders}"
        )


@pytest.mark.asyncio
class TestPipelineEventStreamRevalidation:
    """A revoked session must not keep an open stream (#69, related section)."""

    @staticmethod
    def _wire_saas_auth(monkeypatch, mock_session, db_user):
        """Run the real SaaS auth path against a controlled user row."""
        monkeypatch.setattr("app.config.settings.self_hosted", False)
        monkeypatch.setattr(uploads, "STREAM_REVALIDATE_SECONDS", 0)

        class _Factory:
            def __call__(self):
                return self

            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, *exc):
                return False

        monkeypatch.setattr(uploads, "async_session_factory", _Factory())

        async def fake_get_user_by_id(session, user_id):
            return db_user if db_user is not None and db_user.id == user_id else None

        return patch.object(user_service, "get_user_by_id", fake_get_user_by_id)

    async def _run(self, monkeypatch, mock_session, broker, user, db_user):
        await event_service.publish_pipeline_event(
            "art-owner", "classify", "completed", user_id=user.id
        )
        cookies = {ACCESS_TOKEN_COOKIE: create_access_token(user.id, user.role, user.tier)}
        request = _FakeRequest(disconnect_after=2, cookies=cookies)
        with self._wire_saas_auth(monkeypatch, mock_session, db_user):
            return await _drain(uploads.pipeline_event_stream(request, "", user))

    async def test_live_session_keeps_streaming(self, broker, make_user, monkeypatch, mock_session):
        """Positive control: revalidation does not break a valid session."""
        owner = make_user(id=OWNER_ID, email="owner@example.com", username="owner")

        payloads = await self._run(monkeypatch, mock_session, broker, owner, owner)

        assert [p["artifact_id"] for p in payloads] == ["art-owner"], (
            "periodic revalidation closed a perfectly good stream"
        )

    async def test_password_change_closes_the_stream(
        self, broker, make_user, monkeypatch, mock_session
    ):
        """`tokens_valid_from` moving forward ends the connection."""
        owner = make_user(id=OWNER_ID, email="owner@example.com", username="owner")
        revoked = make_user(
            id=OWNER_ID,
            email="owner@example.com",
            username="owner",
            tokens_valid_from=datetime.now(UTC) + timedelta(seconds=5),
        )

        payloads = await self._run(monkeypatch, mock_session, broker, owner, revoked)

        assert payloads == [], "a session revoked by password change kept reading events"

    async def test_deactivated_account_closes_the_stream(
        self, broker, make_user, monkeypatch, mock_session
    ):
        """A deactivated account loses its open stream too."""
        owner = make_user(id=OWNER_ID, email="owner@example.com", username="owner")
        disabled = make_user(
            id=OWNER_ID, email="owner@example.com", username="owner", is_active=False
        )

        payloads = await self._run(monkeypatch, mock_session, broker, owner, disabled)

        assert payloads == [], "a deactivated account kept reading events"

    async def test_deleted_user_closes_the_stream(
        self, broker, make_user, monkeypatch, mock_session
    ):
        """The user row disappearing ends the connection rather than being ignored."""
        owner = make_user(id=OWNER_ID, email="owner@example.com", username="owner")

        payloads = await self._run(monkeypatch, mock_session, broker, owner, None)

        assert payloads == [], "a stream survived its user being deleted"
