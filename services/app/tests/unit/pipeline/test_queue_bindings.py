"""Queues must not share an exchange+routing key (GL#51 regression).

With bare ``Queue(name)`` every queue bound to the default exchange/routing key,
so on a direct exchange one publish was delivered to every queue and each task
ran several times.
"""

import pytest
from kombu import Connection

from app import worker
from app.worker import ALL_QUEUES, celery_app


def _declared():
    return list(celery_app.amqp.queues.values())


class TestDeclaredBindings:
    def test_each_queue_has_a_unique_exchange_and_routing_key(self):
        pairs = [(q.exchange.name, q.routing_key) for q in _declared()]
        assert len(set(pairs)) == len(pairs), pairs

    def test_each_queue_is_bound_by_its_own_name(self):
        for q in _declared():
            assert q.exchange.name == q.name
            assert q.routing_key == q.name

    def test_defaults_match_the_pipeline_queue(self):
        conf = celery_app.conf
        assert conf.task_default_queue == worker.PIPELINE_QUEUE
        assert conf.task_default_exchange == worker.PIPELINE_QUEUE
        assert conf.task_default_routing_key == worker.PIPELINE_QUEUE


class TestPublishLandsInExactlyOneQueue:
    @pytest.mark.parametrize("name", sorted(worker.TASK_ROUTES))
    def test_routed_message_reaches_only_its_queue(self, name, monkeypatch):
        # The result backend is Redis; do not open a socket to subscribe.
        monkeypatch.setattr(type(celery_app.backend), "on_task_call", lambda *a, **k: None)
        expected = worker.TASK_ROUTES[name]["queue"]
        with Connection("memory://") as conn, conn.channel() as channel:
            bound = [q(channel) for q in _declared()]
            for q in bound:
                q.declare()
            with conn.Producer(channel=channel) as producer:
                celery_app.send_task(name, producer=producer, args=[], kwargs={})
            landed = {}
            for q in bound:
                n = 0
                while q.get(no_ack=True) is not None:
                    n += 1
                landed[q.name] = n
        assert landed == {q: int(q == expected) for q in ALL_QUEUES}, landed


class TestDeclaredAddressLandsInExactlyOneQueue:
    """Publish to each queue's own (exchange, routing_key), as an explicitly
    addressed publisher would. Celery's anonymous-exchange shortcut hides a
    shared binding; this does not."""

    @pytest.mark.parametrize("target", ALL_QUEUES)
    def test_queue_address_reaches_only_that_queue(self, target):
        with Connection("memory://") as conn, conn.channel() as channel:
            bound = [q(channel) for q in _declared()]
            for q in bound:
                q.declare()
            addr = next(q for q in bound if q.name == target)
            with conn.Producer(channel=channel) as producer:
                producer.publish(
                    {"x": 1},
                    exchange=addr.exchange.name,
                    routing_key=addr.routing_key,
                    declare=[],
                )
            landed = {}
            for q in bound:
                n = 0
                while q.get(no_ack=True) is not None:
                    n += 1
                landed[q.name] = n
        assert landed == {q: int(q == target) for q in ALL_QUEUES}, landed
