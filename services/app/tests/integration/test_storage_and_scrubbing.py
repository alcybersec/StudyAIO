"""Storage backends on a real filesystem (and a fake S3), plus credential scrubbing for Sentry.

Storage is where the "never delete user data outside an explicit action" floor
meets the disk, so prefix deletion is checked for what it must *not* touch.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from app.core import observability, storage
from app.core.storage import (
    LocalStorageBackend,
    S3StorageBackend,
    get_storage,
    normalize_storage_key,
    reset_storage,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestLocalBackend:
    async def test_round_trip_and_nested_directories(self, tmp_path):
        backend = LocalStorageBackend(str(tmp_path))
        await backend.put("a/b/c.txt", b"hello")
        assert await backend.exists("a/b/c.txt")
        assert await backend.get("a/b/c.txt") == b"hello"
        assert backend.resolve_path("a/b/c.txt") == tmp_path / "a/b/c.txt"
        assert backend.base_dir == tmp_path
        assert backend.get_url("a/b/c.txt") == "/api/files/a/b/c.txt"

        source = tmp_path / "src.bin"
        source.write_bytes(b"\x00\x01")
        await backend.put_file("copy/src.bin", source)
        out = tmp_path / "elsewhere" / "dest.bin"
        await backend.get_to_file("copy/src.bin", out)
        assert out.read_bytes() == b"\x00\x01"
        await backend.ensure_dir("empty/dir")
        assert (tmp_path / "empty/dir").is_dir()

    async def test_delete_removes_only_the_file(self, tmp_path):
        backend = LocalStorageBackend(str(tmp_path))
        await backend.put("keep/one.txt", b"1")
        await backend.put("keep/two.txt", b"2")
        await backend.delete("keep/one.txt")
        await backend.delete("keep/never-existed.txt")  # no error
        await backend.delete("keep")  # a directory is not a file: untouched
        assert not await backend.exists("keep/one.txt")
        assert await backend.exists("keep/two.txt")

    async def test_delete_prefix_is_scoped_and_counts_files(self, tmp_path):
        backend = LocalStorageBackend(str(tmp_path))
        for key in ("u/1/a", "u/1/b/c", "u/2/a", "other/x"):
            await backend.put(key, b"x")
        assert await backend.delete_prefix("u/1") == 2
        assert await backend.exists("u/2/a") and await backend.exists("other/x")
        assert await backend.delete_prefix("u/1") == 0  # already gone
        assert await backend.delete_prefix("other/x") == 1  # a single file prefix
        assert not await backend.exists("other/x")

    async def test_delete_prefix_refuses_to_leave_the_storage_root(self, tmp_path):
        root = tmp_path / "root"
        outside = tmp_path / "precious"
        outside.mkdir()
        (outside / "thesis.docx").write_bytes(b"irreplaceable")
        backend = LocalStorageBackend(str(root))
        assert await backend.delete_prefix("../precious") == 0
        assert (outside / "thesis.docx").read_bytes() == b"irreplaceable"

    async def test_sync_wrappers_work_outside_an_event_loop(self, tmp_path):
        import asyncio
        import threading

        backend = LocalStorageBackend(str(tmp_path))
        result: dict = {}

        def worker():  # a thread with no running loop, like a Celery task body
            backend.put_sync("w/file.txt", b"data")
            src = tmp_path / "s.txt"
            src.write_text("zzz")
            backend.put_file_sync("w/copy.txt", src)
            dest = tmp_path / "out" / "d.txt"
            backend.get_to_file_sync("w/file.txt", dest)
            result["exists"] = backend.exists_sync("w/file.txt")
            result["missing"] = backend.exists_sync("w/nope.txt")
            result["dest"] = dest.read_bytes()

        thread = threading.Thread(target=worker)
        thread.start()
        await asyncio.get_running_loop().run_in_executor(None, thread.join)
        assert result == {"exists": True, "missing": False, "dest": b"data"}
        assert (tmp_path / "w/copy.txt").read_text() == "zzz"


class FakeS3Client:
    """The slice of boto3's S3 client the backend uses, backed by a dict."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.calls: list[tuple] = []

    def put_object(self, Bucket, Key, Body):  # noqa: N803
        self.objects[Key] = Body

    def upload_file(self, filename, bucket, key):
        self.objects[key] = Path(filename).read_bytes()

    def get_object(self, Bucket, Key):  # noqa: N803
        data = self.objects[Key]
        return {"Body": type("B", (), {"read": staticmethod(lambda: data)})}

    def download_file(self, bucket, key, filename):
        Path(filename).write_bytes(self.objects[key])

    def head_object(self, Bucket, Key):  # noqa: N803
        if Key not in self.objects:
            raise KeyError(Key)

    def delete_object(self, Bucket, Key):  # noqa: N803
        self.objects.pop(Key, None)

    def get_paginator(self, name):
        outer = self

        class Paginator:
            def paginate(self, Bucket, Prefix):  # noqa: N803
                keys = sorted(k for k in outer.objects if k.startswith(Prefix))
                yield {"Contents": [{"Key": k} for k in keys[:2]]} if keys else {}
                if len(keys) > 2:
                    yield {"Contents": [{"Key": k} for k in keys[2:]]}

        return Paginator()

    def delete_objects(self, Bucket, Delete):  # noqa: N803
        for obj in Delete["Objects"]:
            self.objects.pop(obj["Key"], None)
        self.calls.append(("delete_objects", len(Delete["Objects"])))

    def generate_presigned_url(self, op, Params, ExpiresIn):  # noqa: N803
        return f"https://signed.example/{Params['Key']}?exp={ExpiresIn}"


class TestS3Backend:
    @pytest.fixture
    def s3(self):
        fake = FakeS3Client()
        backend = S3StorageBackend()
        backend._client = fake
        with (
            patch("app.config.settings.s3_bucket", "bucket"),
            patch("app.config.settings.s3_prefix", "/studyaio/"),
            patch("app.config.settings.cdn_base_url", ""),
        ):
            yield backend, fake

    async def test_keys_are_namespaced_and_round_trip(self, s3, tmp_path):
        backend, fake = s3
        await backend.put("uploads/a.pdf", b"pdf")
        assert set(fake.objects) == {"studyaio/uploads/a.pdf"}
        assert await backend.get("uploads/a.pdf") == b"pdf"
        assert await backend.exists("uploads/a.pdf") and not await backend.exists("uploads/b.pdf")
        src = tmp_path / "s"
        src.write_bytes(b"file")
        await backend.put_file("uploads/b.pdf", src)
        dest = tmp_path / "nested" / "d"
        await backend.get_to_file("uploads/b.pdf", dest)
        assert dest.read_bytes() == b"file"
        await backend.ensure_dir("anything")  # no-op
        await backend.delete("uploads/a.pdf")
        await backend.delete("uploads/never")  # absent keys are fine
        assert "studyaio/uploads/a.pdf" not in fake.objects

    async def test_delete_prefix_pages_and_stays_in_its_prefix(self, s3):
        backend, fake = s3
        for i in range(5):
            fake.objects[f"studyaio/u/1/{i}"] = b"x"
        fake.objects["studyaio/u/2/0"] = b"keep"
        assert await backend.delete_prefix("u/1") == 5
        assert set(fake.objects) == {"studyaio/u/2/0"}
        assert await backend.delete_prefix("u/9") == 0

    async def test_urls_prefer_the_cdn_then_fall_back_to_presigned(self, s3):
        backend, _ = s3
        assert backend.get_url("k").startswith("https://signed.example/studyaio/k")
        with patch("app.config.settings.cdn_base_url", "https://cdn.example/"):
            assert backend.get_url("k") == "https://cdn.example/studyaio/k"

    async def test_client_is_built_lazily_from_settings(self):
        backend = S3StorageBackend()
        captured = {}
        with (
            patch("boto3.client", lambda name, **kw: captured.update(kw) or object()),
            patch("app.config.settings.s3_region", "eu-west-1"),
            patch("app.config.settings.s3_access_key_id", "AKIA"),
            patch("app.config.settings.s3_secret_access_key", SecretStr("sekret")),
            patch("app.config.settings.s3_endpoint_url", "http://minio:9000"),
        ):
            first = backend._get_client()
            assert backend._get_client() is first
        assert captured == {
            "region_name": "eu-west-1",
            "aws_access_key_id": "AKIA",
            "aws_secret_access_key": "sekret",
            "endpoint_url": "http://minio:9000",
        }


class TestAccessorAndKeys:
    async def test_backend_selection_is_memoised_and_resettable(self):
        reset_storage()
        with patch("app.config.settings.storage_backend", "s3"):
            first = get_storage()
            assert isinstance(first, S3StorageBackend) and get_storage() is first
        reset_storage()
        assert isinstance(get_storage(), LocalStorageBackend)
        reset_storage()

    async def test_normalize_strips_the_data_dir_only(self):
        from app.config import settings

        data_dir = settings.data_dir.rstrip("/")
        assert normalize_storage_key(f"{data_dir}/uploads/x.pdf") == "uploads/x.pdf"
        assert normalize_storage_key("uploads/x.pdf") == "uploads/x.pdf"
        assert normalize_storage_key("/elsewhere/uploads/x.pdf") == "/elsewhere/uploads/x.pdf"
        assert storage.StorageBackend.__abstractmethods__  # the contract stays abstract


class TestSentryScrubbing:
    async def test_credentials_never_leave_the_process(self):
        event = {
            "request": {
                "headers": {
                    "Cookie": "access_token=SECRET",
                    "Authorization": "Bearer X",
                    "Accept": "json",
                },
                "cookies": {"access_token": "SECRET"},
                "query_string": "token=RAW&page=2&invite_code=BETA-1",
                "url": "https://app.example/reset?token=RAW&x=1",
                "data": {"password": "hunter2", "email": "a@x.com", "TOTP_CODE": "123456"},
            },
            "extra": {"api_key": "sk-1", "note": "fine"},
            "tags": {"secret": "s", "component": "api"},
        }
        out = observability.scrub_event(event, {})
        request = out["request"]
        assert request["headers"]["Cookie"] == observability.FILTERED
        assert request["headers"]["Authorization"] == observability.FILTERED
        assert request["headers"]["Accept"] == "json"
        assert "cookies" not in request
        assert "RAW" not in request["query_string"] and "page=2" in request["query_string"]
        assert "BETA-1" not in request["query_string"]
        assert "RAW" not in request["url"] and "x=1" in request["url"]
        assert request["data"] == {
            "password": observability.FILTERED,
            "email": "a@x.com",
            "TOTP_CODE": observability.FILTERED,
        }
        assert out["extra"] == {"api_key": observability.FILTERED, "note": "fine"}
        assert out["tags"]["secret"] == observability.FILTERED and out["tags"]["component"] == "api"

    async def test_scrubbing_tolerates_odd_events(self):
        assert observability.scrub_event({}, {}) == {}
        odd = {"request": {"headers": "not-a-dict", "query_string": 5, "url": "no-query"}}
        assert observability.scrub_event(odd, {}) == odd
        assert observability._scrub_query("") == ""
        assert observability._scrub_query("novalue").startswith("novalue")

    async def test_sentry_is_inert_without_a_dsn_and_never_raises(self):
        observability._initialized = False
        with patch("app.config.settings.sentry_dsn", ""):
            assert observability.init_sentry("api") is False
        with (
            patch("app.config.settings.sentry_dsn", "https://k@o.ingest.sentry.io/1"),
            patch.dict("sys.modules", {"sentry_sdk": None}),
        ):
            assert observability.init_sentry("worker") is False
        with (
            patch("app.config.settings.sentry_dsn", "https://k@o.ingest.sentry.io/1"),
            patch("sentry_sdk.init", side_effect=RuntimeError("bad dsn")),
        ):
            assert observability.init_sentry("api") is False
        assert observability._initialized is False

    async def test_init_wires_scrubber_and_component_integrations(self):
        observability._initialized = False
        try:
            with (
                patch("app.config.settings.sentry_dsn", "https://k@o.ingest.sentry.io/1"),
                patch("sentry_sdk.init") as init,
                patch("sentry_sdk.set_tag") as set_tag,
            ):
                assert observability.init_sentry("api") is True
                assert observability.init_sentry("api") is True  # idempotent
            assert init.call_count == 1
            kwargs = init.call_args.kwargs
            assert kwargs["before_send"] is observability.scrub_event
            assert kwargs["send_default_pii"] is False
            assert {type(i).__name__ for i in kwargs["integrations"]} >= {"FastApiIntegration"}
            set_tag.assert_called_once_with("component", "api")
            assert [type(i).__name__ for i in observability._build_integrations("worker")] == [
                "CeleryIntegration"
            ]
            assert observability._build_integrations("other") == []
        finally:
            observability._initialized = False
