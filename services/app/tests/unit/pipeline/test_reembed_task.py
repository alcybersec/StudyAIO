"""Re-embed task (GL#17): per-user, resumable, idempotent, never strands an artifact."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import IndexingError
from app.pipeline import reembed_task as rt

USER = "user-1"


def _provider(window: int = 20) -> MagicMock:
    p = MagicMock()
    p._input_window.return_value = window
    p._word_tokens.side_effect = lambda words: [1 for _ in words]
    p.embed_texts.side_effect = lambda texts: [[0.0] for _ in texts]
    return p


def _scalars(values):
    r = MagicMock()
    r.scalars.return_value.all.return_value = values
    r.scalar_one_or_none.return_value = values[0] if values else None
    return r


def _session_with(results):
    session = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock(side_effect=results)
    return session


@pytest.fixture
def index_env():
    """`_index` with a fake session factory, provider and index_service."""
    artifact = MagicMock(user_id=USER)
    extraction = MagicMock(
        manifest_json={"pages": [{"page_number": 1, "text": "w " * 60, "images": []}]}
    )
    with (
        patch("app.pipeline.index.async_session_factory") as factory,
        patch("app.pipeline.index.get_embedding_provider") as get_provider,
        patch("app.pipeline.index.index_service.index_artifact_chunks", new=AsyncMock()) as write,
    ):
        factory.return_value.__aenter__ = AsyncMock()
        factory.return_value.__aexit__ = AsyncMock(return_value=False)
        get_provider.return_value = _provider()

        def set_stored(stored_chunks, rewritten=None):
            session = _session_with(
                [_scalars([artifact]), _scalars([extraction]), _scalars(stored_chunks)]
            )
            factory.return_value.__aenter__.return_value = session
            write.return_value = [MagicMock()] if rewritten is None else rewritten
            return session

        yield set_stored, write, artifact


class TestIndexRefreshMode:
    async def test_fitting_artifact_is_left_alone(self, index_env):
        from app.pipeline.index import _index

        set_stored, write, artifact = index_env
        session = set_stored(["short chunk"])
        out = await _index("a1", USER, refresh="apply")
        assert out["status"] == "skipped_fit"
        write.assert_not_called()
        session.commit.assert_not_called()
        assert artifact.status != "indexing"  # status machine untouched

    async def test_stale_artifact_rewritten_then_committed(self, index_env):
        from app.pipeline.index import _index

        set_stored, write, artifact = index_env
        session = set_stored([" ".join(["w"] * 40)])
        order: list[str] = []
        write.side_effect = lambda **kw: order.append("write") or [MagicMock(), MagicMock()]
        session.commit.side_effect = lambda: order.append("commit")
        out = await _index("a1", USER, refresh="apply")
        assert out == {"artifact_id": "a1", "status": "reembedded", "chunk_count": 2}
        assert order == ["write", "commit"]  # nothing committed before the new rows exist
        assert write.await_args.kwargs["artifact_id"] == "a1"

    async def test_dry_run_writes_nothing(self, index_env):
        from app.pipeline.index import _index

        set_stored, write, _ = index_env
        session = set_stored([" ".join(["w"] * 40)])
        out = await _index("a1", USER, refresh="dry_run")
        assert out["status"] == "stale"
        write.assert_not_called()
        session.commit.assert_not_called()

    async def test_empty_rechunk_keeps_old_chunks(self, index_env):
        from app.pipeline.index import _index

        set_stored, _, _ = index_env
        session = set_stored([" ".join(["w"] * 40)], rewritten=[])
        out = await _index("a1", USER, refresh="apply")
        assert out["status"] == "skipped_no_text"
        session.commit.assert_not_called()
        session.rollback.assert_awaited()


class TestReembedArtifact:
    async def test_passes_owner_and_mode_to_index(self):
        with patch.object(
            rt, "_index", new=AsyncMock(return_value={"status": "reembedded"})
        ) as idx:
            assert await rt._reembed_artifact("a1", USER, dry_run=False) == "reembedded"
        idx.assert_awaited_once_with("a1", USER, refresh="apply")

    async def test_dry_run_mode(self):
        with patch.object(rt, "_index", new=AsyncMock(return_value={"status": "stale"})) as idx:
            assert await rt._reembed_artifact("a1", USER, dry_run=True) == "reembedded"
        assert idx.await_args.kwargs["refresh"] == "dry_run"

    async def test_missing_extraction_is_skipped_not_failed(self):
        with patch.object(rt, "_index", new=AsyncMock(side_effect=IndexingError("No extraction"))):
            assert await rt._reembed_artifact("a1", USER, False) == "skipped_no_extraction"


class TestArtifactPageIsScoped:
    async def test_query_filters_on_user_id(self):
        session = AsyncMock()
        session.execute.return_value = _scalars(["a1"])
        await rt._artifact_page(session, USER, None, 10)
        stmt = session.execute.await_args.args[0]
        assert USER in stmt.compile().params.values()


class TestReembedUser:
    async def test_walks_pages_and_counts_outcomes(self):
        pages = AsyncMock(side_effect=[["a1", "a2"], ["a3"], []])
        outcomes = AsyncMock(side_effect=["reembedded", "skipped_fit", RuntimeError("boom")])
        with (
            patch.object(rt, "async_session_factory"),
            patch.object(rt, "_artifact_page", new=pages),
            patch.object(rt, "_reembed_artifact", new=outcomes),
        ):
            out = await rt.reembed_user_chunks_async(USER, batch_size=2)
        assert (out["scanned"], out["reembedded"], out["skipped_fit"], out["failed"]) == (
            3,
            1,
            1,
            1,
        )
        # keyset-resumable: page two starts after the last id of page one
        assert pages.await_args_list[1].args[2] == "a2"
        # every page query and every rewrite carries the user
        assert all(c.args[1] == USER for c in pages.await_args_list)
        assert all(c.args[1] == USER for c in outcomes.await_args_list)

    async def test_one_failure_does_not_stop_the_run(self):
        outcomes = AsyncMock(side_effect=[RuntimeError("boom"), "reembedded"])
        with (
            patch.object(rt, "async_session_factory"),
            patch.object(rt, "_artifact_page", new=AsyncMock(side_effect=[["a1", "a2"], []])),
            patch.object(rt, "_reembed_artifact", new=outcomes),
        ):
            out = await rt.reembed_user_chunks_async(USER)
        assert out["failed"] == 1
        assert out["reembedded"] == 1


class TestEntryPoints:
    def test_tasks_are_registered_by_name(self):
        assert rt.reembed_user_chunks.name == "app.pipeline.reembed_task.reembed_user_chunks"
        assert rt.reembed_all_chunks.name == "app.pipeline.reembed_task.reembed_all_chunks"

    def test_worker_includes_the_module(self):
        from app.worker import celery_app

        assert "app.pipeline.reembed_task" in celery_app.conf.include

    def test_cli_enqueues_for_one_user(self):
        with patch.object(rt.reembed_user_chunks, "delay") as delay:
            assert rt.main(["--user-id", USER, "--batch-size", "5"]) == 0
        delay.assert_called_once_with(USER, 5)

    def test_cli_enqueues_for_all(self):
        with patch.object(rt.reembed_all_chunks, "delay") as delay:
            assert rt.main([]) == 0
        delay.assert_called_once_with(rt.DEFAULT_BATCH_SIZE)

    def test_all_task_fans_out_one_per_user(self):
        with (
            patch.object(rt, "_all_user_ids", new=AsyncMock(return_value=["u1", "u2"])),
            patch.object(rt.reembed_user_chunks, "delay") as delay,
        ):
            out = rt.reembed_all_chunks.run(7)
        assert out == {"users_enqueued": 2}
        assert [c.args for c in delay.call_args_list] == [("u1", 7), ("u2", 7)]
