"""Queue split: every task is routed, beat jobs are on maintenance (TECH-09, GL#51)."""

import pytest

from app import worker
from app.pipeline.limits import STAGE_TIME_LIMITS
from app.worker import (
    AI_ONDEMAND_QUEUE,
    ALL_QUEUES,
    LEGACY_QUEUE,
    MAINTENANCE_QUEUE,
    PIPELINE_QUEUE,
    celery_app,
)


def _registered_tasks() -> set[str]:
    celery_app.loader.import_default_modules()
    return {n for n in celery_app.tasks if not n.startswith("celery.")}


def _queue_of(name: str) -> str:
    return celery_app.amqp.router.route({}, name)["queue"].name


class TestRoutingTable:
    def test_every_registered_task_has_an_explicit_route(self):
        missing = _registered_tasks() - set(worker.TASK_ROUTES)
        assert not missing, f"tasks without a queue route: {sorted(missing)}"

    def test_no_route_for_an_unregistered_task(self):
        stale = set(worker.TASK_ROUTES) - _registered_tasks()
        assert not stale, f"routes for tasks that do not exist: {sorted(stale)}"

    def test_every_route_targets_a_declared_queue(self):
        declared = {q.name for q in celery_app.conf.task_queues}
        for name, route in worker.TASK_ROUTES.items():
            assert route["queue"] in declared, name

    def test_nothing_routes_to_the_legacy_queue(self):
        assert all(r["queue"] != LEGACY_QUEUE for r in worker.TASK_ROUTES.values())
        assert celery_app.conf.task_default_queue != LEGACY_QUEUE

    def test_single_worker_list_covers_every_queue_in_use(self):
        listed = set(worker.SINGLE_WORKER_QUEUES.split(","))
        used = {r["queue"] for r in worker.TASK_ROUTES.values()}
        assert used | {celery_app.conf.task_default_queue} <= listed
        assert listed == set(ALL_QUEUES)

    @pytest.mark.parametrize("name", sorted(worker.TASK_ROUTES))
    def test_router_resolves_each_task_to_its_queue(self, name):
        assert _queue_of(name) == worker.TASK_ROUTES[name]["queue"]


class TestQueueAssignment:
    def test_beat_jobs_all_run_on_maintenance(self):
        for entry, spec in celery_app.conf.beat_schedule.items():
            assert _queue_of(spec["task"]) == MAINTENANCE_QUEUE, entry

    @pytest.mark.parametrize(
        "stage",
        [
            "ingest.ingest_file",
            "classify.classify_artifact",
            "extract.extract_artifact",
            "summarize.summarize_artifact",
            "index.index_artifact",
            "assets.generate_assets",
        ],
    )
    def test_chain_stages_run_on_pipeline(self, stage):
        assert _queue_of(f"app.pipeline.{stage}") == PIPELINE_QUEUE

    def test_targeted_generation_is_not_on_the_pipeline_queue(self):
        name = "app.pipeline.targeted_task.generate_targeted_items"
        assert _queue_of(name) == AI_ONDEMAND_QUEUE

    def test_unrouted_task_defaults_to_pipeline(self):
        assert celery_app.conf.task_default_queue == PIPELINE_QUEUE


class TestDeliverySemantics:
    def test_prefetch_one_and_acks_late(self):
        assert celery_app.conf.worker_prefetch_multiplier == 1
        assert celery_app.conf.task_acks_late is True

    def test_time_limits_still_apply_to_routed_tasks(self):
        ann = celery_app.conf.task_annotations
        for name, (soft, hard) in STAGE_TIME_LIMITS.items():
            assert name in worker.TASK_ROUTES
            assert ann[name] == {"soft_time_limit": soft, "time_limit": hard}

    def test_visibility_timeout_exceeds_longest_hard_limit(self):
        longest = max(hard for _, hard in STAGE_TIME_LIMITS.values())
        vt = celery_app.conf.broker_transport_options["visibility_timeout"]
        assert vt > longest
