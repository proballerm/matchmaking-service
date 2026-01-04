from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from core.models import Match
from core.queue import MatchmakingQueue


class Matchmaker:
    """
    Matchmaker with adaptive rating threshold and SLA enforcement.
    """

    def __init__(
        self,
        base_threshold: float = 100.0,
        min_threshold: float = 50.0,
        max_threshold: float = 400.0,
        target_avg_wait: float = 5.0,
        adapt_rate: float = 10.0,
        max_wait_time: float = 20.0,
    ):
        self.base_threshold = base_threshold
        self.current_threshold = base_threshold
        self.min_threshold = min_threshold
        self.max_threshold = max_threshold
        self.target_avg_wait = target_avg_wait
        self.adapt_rate = adapt_rate
        self.max_wait_time = max_wait_time

    def adapt_threshold(self, avg_wait_time: float) -> None:
        error = avg_wait_time - self.target_avg_wait
        self.current_threshold += self.adapt_rate * error

        self.current_threshold = max(
            self.min_threshold,
            min(self.max_threshold, self.current_threshold),
        )

    def try_form_matches(self, queue: MatchmakingQueue) -> List[Match]:
        entries = sorted(queue.get_entries(), key=lambda e: e.join_time)
        matches: List[Match] = []
        used_players = set()

        for i in range(len(entries)):
            a = entries[i]
            if a.player_id in used_players:
                continue

            for j in range(i + 1, len(entries)):
                b = entries[j]
                if b.player_id in used_players:
                    continue

                if abs(a.rating - b.rating) <= self.current_threshold:
                    matches.append(Match.create([a.player_id, b.player_id]))
                    used_players.add(a.player_id)
                    used_players.add(b.player_id)
                    break

        if matches:
            matched_ids = [pid for m in matches for pid in m.player_ids]
            queue.remove_players(matched_ids)

        return matches

    def enforce_sla(self, queue: MatchmakingQueue, now: datetime) -> List[Match]:
        """
        Force matches for players who exceeded max wait time.
        SLA matches do not depend on current_threshold.
        """
        # Normalize now to timezone-aware UTC (defensive)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        else:
            now = now.astimezone(timezone.utc)

        matches: List[Match] = []

        # Work off a local view of entries and update it after removals.
        entries = sorted(queue.get_entries(), key=lambda e: e.join_time)

        while len(entries) >= 2:
            oldest = entries[0]
            wait_time = (now - oldest.join_time).total_seconds()

            if wait_time < self.max_wait_time:
                break

            partner = min(entries[1:], key=lambda e: abs(e.rating - oldest.rating))
            matches.append(Match.create([oldest.player_id, partner.player_id]))

            queue.remove_players([oldest.player_id, partner.player_id])

            # Refresh entries after removal
            entries = sorted(queue.get_entries(), key=lambda e: e.join_time)

        return matches
