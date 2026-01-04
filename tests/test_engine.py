from datetime import datetime, timedelta, timezone

from core.engine import MatchmakingEngine
from core.matcher import Matchmaker


class FakeClock:
    def __init__(self, start: datetime):
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now = self._now + timedelta(seconds=seconds)


def test_enqueue_idempotent():
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    engine = MatchmakingEngine(now_fn=clock.now)

    assert engine.enqueue_player("p1", 1000) is True
    assert engine.enqueue_player("p1", 1000) is False
    assert engine.get_metrics()["queue_depth"] == 1.0


def test_normal_match_within_threshold():
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    mm = Matchmaker(base_threshold=100.0)
    engine = MatchmakingEngine(matchmaker=mm, now_fn=clock.now)

    engine.enqueue_player("p1", 1000)
    engine.enqueue_player("p2", 1050)

    new = engine.run_matchmaking_once()
    assert len(new) == 1
    assert engine.get_metrics()["queue_depth"] == 0.0

    out = engine.get_and_clear_matches()
    assert len(out) == 1
    assert engine.get_and_clear_matches() == []


def test_no_match_outside_threshold():
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    mm = Matchmaker(base_threshold=10.0, min_threshold=10.0, max_threshold=10.0)
    engine = MatchmakingEngine(matchmaker=mm, now_fn=clock.now)

    engine.enqueue_player("p1", 1000)
    engine.enqueue_player("p2", 2000)

    new = engine.run_matchmaking_once()
    assert new == []
    assert engine.get_metrics()["queue_depth"] == 2.0


def test_sla_forces_match_after_max_wait():
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    mm = Matchmaker(base_threshold=10.0, min_threshold=10.0, max_threshold=10.0, max_wait_time=20.0)
    engine = MatchmakingEngine(matchmaker=mm, now_fn=clock.now)

    engine.enqueue_player("old", 1000)
    engine.enqueue_player("new", 1600)

    clock.advance(25.0)
    new = engine.run_matchmaking_once()

    assert len(new) == 1
    assert new[0].sla_forced is True
    assert engine.get_metrics()["queue_depth"] == 0.0


def test_sla_does_not_affect_threshold():
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    mm = Matchmaker(base_threshold=50.0, min_threshold=50.0, max_threshold=400.0, max_wait_time=5.0, adapt_rate=10.0)
    engine = MatchmakingEngine(matchmaker=mm, now_fn=clock.now)

    engine.enqueue_player("p1", 1000)
    engine.enqueue_player("p2", 2000)

    before = mm.current_threshold
    clock.advance(10.0)
    engine.run_matchmaking_once()
    after = mm.current_threshold

    assert before == after
