from datetime import datetime, timezone

import fakeredis

from core.match_store import InMemoryMatchStore, RedisMatchStore
from core.models import MatchRecord


def make_match(match_id: str = "m1") -> MatchRecord:
    return MatchRecord(
        match_id=match_id,
        player_ids=("p1", "p2"),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        rating_diff=25.0,
        sla_forced=False,
        threshold_at_match=100.0,
    )


def test_memory_delivery_is_acknowledged_and_cleaned_per_player():
    store = InMemoryMatchStore()
    match = make_match()
    store.publish(match)

    assert store.get_pending("p1") == [match]
    assert store.get_pending("p2") == [match]

    assert store.acknowledge("p1", match.match_id) is True
    assert store.get_pending("p1") == []
    assert store.get_pending("p2") == [match]
    assert match.match_id in store._matches

    assert store.acknowledge("p2", match.match_id) is True
    assert store.get_pending("p2") == []
    assert match.match_id not in store._matches
    assert match.match_id not in store._remaining_acknowledgements


def test_redis_delivery_survives_store_recreation_and_cleans_up():
    client = fakeredis.FakeRedis(decode_responses=True)
    RedisMatchStore(client, namespace="delivery").publish(make_match())

    restarted = RedisMatchStore(client, namespace="delivery")
    assert [match.match_id for match in restarted.get_pending("p1")] == ["m1"]
    assert [match.match_id for match in restarted.get_pending("p2")] == ["m1"]
    assert client.hget(restarted.remaining_acks_key, "m1") == "2"

    assert restarted.acknowledge("p1", "m1") is True
    assert restarted.get_pending("p1") == []
    assert [match.match_id for match in restarted.get_pending("p2")] == ["m1"]
    assert client.hexists(restarted.matches_key, "m1")
    assert client.hget(restarted.remaining_acks_key, "m1") == "1"

    assert restarted.acknowledge("p2", "m1") is True
    assert restarted.get_pending("p2") == []
    assert not client.hexists(restarted.matches_key, "m1")
    assert not client.hexists(restarted.remaining_acks_key, "m1")


def test_duplicate_acknowledgement_does_not_delete_early():
    client = fakeredis.FakeRedis(decode_responses=True)
    store = RedisMatchStore(client, namespace="duplicate")
    store.publish(make_match())

    assert store.acknowledge("p1", "m1") is True
    assert store.acknowledge("p1", "m1") is False
    assert client.hget(store.remaining_acks_key, "m1") == "1"
    assert client.hexists(store.matches_key, "m1")
    assert [match.match_id for match in store.get_pending("p2")] == ["m1"]


def test_acknowledgement_is_scoped_to_player():
    client = fakeredis.FakeRedis(decode_responses=True)
    store = RedisMatchStore(client, namespace="scope")
    store.publish(make_match())

    assert store.acknowledge("other-player", "m1") is False
    assert client.hget(store.remaining_acks_key, "m1") == "2"
    assert [match.match_id for match in store.get_pending("p1")] == ["m1"]
