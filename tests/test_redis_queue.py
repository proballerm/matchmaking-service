from datetime import datetime, timedelta, timezone

import fakeredis
import pytest

from core.redis_queue import RedisMatchmakingQueue


def make_queue() -> RedisMatchmakingQueue:
    return RedisMatchmakingQueue(fakeredis.FakeRedis(decode_responses=True), namespace="test")


def test_add_get_and_remove_players():
    queue = make_queue()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    queue.add_player("p2", 1300, now + timedelta(seconds=2))
    queue.add_player("p1", 1200, now)

    entries = queue.get_entries()
    assert [entry.player_id for entry in entries] == ["p1", "p2"]
    assert [entry.rating for entry in entries] == [1200.0, 1300.0]
    assert queue.size() == 2

    queue.remove_players(["p1"])
    assert [entry.player_id for entry in queue.get_entries()] == ["p2"]
    assert queue.size() == 1


def test_duplicate_player_is_rejected():
    queue = make_queue()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    queue.add_player("p1", 1200, now)
    with pytest.raises(ValueError, match="already queued"):
        queue.add_player("p1", 1500, now + timedelta(seconds=1))

    entry = queue.get_entries()[0]
    assert entry.rating == 1200.0


def test_naive_datetime_is_rejected():
    queue = make_queue()

    with pytest.raises(ValueError, match="timezone-aware UTC"):
        queue.add_player("p1", 1200, datetime(2026, 1, 1))


def test_clear_removes_queue_and_metadata():
    queue = make_queue()
    queue.add_player("p1", 1200, datetime(2026, 1, 1, tzinfo=timezone.utc))

    queue.clear()

    assert queue.get_entries() == []
    assert queue.size() == 0
