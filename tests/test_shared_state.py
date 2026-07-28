from datetime import datetime, timedelta, timezone

import fakeredis

from core.engine import MatchmakingEngine
from core.match_store import RedisMatchStore
from core.redis_queue import RedisMatchmakingQueue
from core.state_store import RedisStateStore


def build_engine(client, namespace: str) -> MatchmakingEngine:
    queue = RedisMatchmakingQueue(client, namespace=namespace)
    return MatchmakingEngine(
        queue=queue,
        match_store=RedisMatchStore(client, namespace=namespace),
        state_store=RedisStateStore(client, namespace=namespace),
    )


def test_workers_share_counters_and_threshold():
    client = fakeredis.FakeRedis(decode_responses=True)
    worker_a = build_engine(client, "shared")
    worker_b = build_engine(client, "shared")
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert worker_a.enqueue_player("p1", 1200, now - timedelta(seconds=10))
    assert worker_b.enqueue_player("p2", 1210, now - timedelta(seconds=10))

    worker_a.run_matchmaking_once(now)

    metrics_a = worker_a.get_metrics()
    metrics_b = worker_b.get_metrics()
    assert metrics_a == metrics_b
    assert metrics_a["total_enqueues"] == 2.0
    assert metrics_a["total_matches"] == 1.0
    assert metrics_a["current_threshold"] == 150.0


def test_threshold_updates_are_atomic_across_stores():
    client = fakeredis.FakeRedis(decode_responses=True)
    store_a = RedisStateStore(client, namespace="atomic")
    store_b = RedisStateStore(client, namespace="atomic")

    assert store_a.adapt_threshold(10.0) == 150.0
    assert store_b.adapt_threshold(10.0) == 200.0
    assert store_a.get_threshold() == 200.0


def test_shared_sla_metrics_are_system_wide():
    client = fakeredis.FakeRedis(decode_responses=True)
    worker_a = build_engine(client, "sla")
    worker_b = build_engine(client, "sla")
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    worker_a.enqueue_player("p1", 1000, now - timedelta(seconds=30))
    worker_b.enqueue_player("p2", 1800, now - timedelta(seconds=30))
    worker_b.run_matchmaking_once(now)

    metrics = worker_a.get_metrics()
    assert metrics["total_matches"] == 1.0
    assert metrics["sla_forced_matches"] == 1.0
    assert metrics["sla_forced_percentage"] == 100.0
