from datetime import datetime, timezone

import fakeredis

from core.engine import MatchmakingEngine
from core.redis_queue import RedisMatchmakingQueue


def test_two_workers_do_not_match_players_twice():
    server = fakeredis.FakeServer()
    queue_a = RedisMatchmakingQueue(
        fakeredis.FakeRedis(server=server, decode_responses=True),
        namespace="workers",
    )
    queue_b = RedisMatchmakingQueue(
        fakeredis.FakeRedis(server=server, decode_responses=True),
        namespace="workers",
    )

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    engine_a = MatchmakingEngine(queue=queue_a)
    engine_b = MatchmakingEngine(queue=queue_b)

    assert engine_a.enqueue_player("p1", 1200, now)
    assert engine_a.enqueue_player("p2", 1210, now)

    matches_a = engine_a.run_matchmaking_once(now)
    matches_b = engine_b.run_matchmaking_once(now)
    all_matches = matches_a + matches_b

    assert len(all_matches) == 1
    assert set(all_matches[0].player_ids) == {"p1", "p2"}
    assert queue_a.size() == 0
