from datetime import datetime, timezone
from core.engine import MatchmakingEngine

engine = MatchmakingEngine()

now = datetime.now(timezone.utc)

engine.enqueue_player("p1", 1200, now)
engine.enqueue_player("p2", 1210, now)
engine.enqueue_player("p3", 2000, now)

new_matches = engine.run_matchmaking_once(now)
print("Created:", new_matches)

print("Poll matches:", engine.get_and_clear_matches())
print("Metrics:", engine.get_metrics())
