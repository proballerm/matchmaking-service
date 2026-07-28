from datetime import datetime, timezone

import fakeredis

from core.engine import MatchmakingEngine
from core.match_store import RedisMatchStore
from core.models import MatchRecord
from core.redis_queue import RedisMatchmakingQueue


def build_components(namespace: str = "atomic"):
    client = fakeredis.FakeRedis(decode_responses=True)
    queue = RedisMatchmakingQueue(client, namespace=namespace)
    store = RedisMatchStore(client, namespace=namespace)
    return client, queue, store


def make_match(match_id: str = "m1") -> MatchRecord:
    return MatchRecord(
        match_id=match_id,
        player_ids=("p1", "p2"),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        rating_diff=20.0,
        sla_forced=False,
        threshold_at_match=100.0,
    )


def test_claim_and_publish_commits_queue_and_inboxes_together():
    _client, queue, store = build_components()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    queue.add_player("p1", 1200, now)
    queue.add_player("p2", 1220, now)

    assert store.claim_and_publish(queue, make_match()) is True
    assert queue.size() == 0
    assert [match.match_id for match in store.get_pending("p1")] == ["m1"]
    assert [match.match_id for match in store.get_pending("p2")] == ["m1"]


def test_failed_claim_writes_no_match_or_inbox_entries():
    client, queue, store = build_components(namespace="failed")
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    queue.add_player("p1", 1200, now)

    assert store.claim_and_publish(queue, make_match()) is False
    assert queue.contains("p1") is True
    assert store.get_pending("p1") == []
    assert store.get_pending("p2") == []
    assert client.hlen(store.matches_key) == 0


def test_engine_uses_atomic_commit_for_match_creation():
    _client, queue, store = build_components(namespace="engine")
    engine = MatchmakingEngine(queue=queue, match_store=store)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert engine.enqueue_player("p1", 1200, now)
    assert engine.enqueue_player("p2", 1220, now)

    matches = engine.run_matchmaking_once(now)

    assert len(matches) == 1
    assert queue.size() == 0
    assert store.get_pending("p1") == matches
    assert store.get_pending("p2") == matches


def test_second_worker_cannot_publish_duplicate_match():
    _client, queue, store = build_components(namespace="race")
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    queue.add_player("p1", 1200, now)
    queue.add_player("p2", 1220, now)

    assert store.claim_and_publish(queue, make_match("winner")) is True
    assert store.claim_and_publish(queue, make_match("duplicate")) is False

    assert [match.match_id for match in store.get_pending("p1")] == ["winner"]
    assert [match.match_id for match in store.get_pending("p2")] == ["winner"]
