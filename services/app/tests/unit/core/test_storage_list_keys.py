"""`StorageBackend.list_keys`: enumerate keys under a prefix (M32 C5 / R-020)."""

from pathlib import Path

import pytest

from app.core.storage import LocalStorageBackend


@pytest.mark.asyncio
async def test_list_keys_returns_every_file_under_prefix(tmp_path: Path) -> None:
    store = LocalStorageBackend(base_dir=str(tmp_path))
    await store.put("ledger/u1/a", b"")
    await store.put("ledger/u1/b", b"")
    await store.put("ledger/u2/c", b"")

    assert sorted(await store.list_keys("ledger/u1")) == ["ledger/u1/a", "ledger/u1/b"]


@pytest.mark.asyncio
async def test_list_keys_missing_prefix_is_empty(tmp_path: Path) -> None:
    store = LocalStorageBackend(base_dir=str(tmp_path))
    assert await store.list_keys("nothing/here") == []


@pytest.mark.asyncio
async def test_list_keys_refuses_to_walk_outside_root(tmp_path: Path) -> None:
    store = LocalStorageBackend(base_dir=str(tmp_path / "root"))
    (tmp_path / "secret.txt").write_text("x")
    assert await store.list_keys("..") == []


@pytest.mark.asyncio
async def test_s3_list_keys_failure_raises_not_empty() -> None:
    """Not being able to look must not read as nothing being there (a purge deletes on [])."""
    from unittest.mock import MagicMock, patch

    from app.core.storage import S3StorageBackend

    store = S3StorageBackend.__new__(S3StorageBackend)
    client = MagicMock()
    client.get_paginator.return_value.paginate.side_effect = RuntimeError("s3 down")
    with patch.object(S3StorageBackend, "_get_client", return_value=client):
        with pytest.raises(RuntimeError):
            await store.list_keys("ledger/x")
