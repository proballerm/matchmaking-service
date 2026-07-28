from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Protocol

from core.models import Match, QueueEntry


class ClaimableQueue(Protocol):
    def get_entries(self) -> List[QueueEntry]: ...
    def claim_players(self, player_ids: List[str]) -> bool: ...


class Matchmaker:
    """Matchmaker with adaptive rating thresholds and SLA enforcement."""

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

    def try_form_matches(self, queue: ClaimableQueue) -> List[Match]:
        entries = sorted(queue.get_entries(), key=lambda entry: entry.join_time)
        matches: List[Match] = []
        unavailable_players = set()

        for index, player_a in enumerate(entries):
            if player_a.player_id in unavailable_players:
                continue

            for player_b in entries[index + 1 :]:
                if player_b.player_id in unavailable_players:
                    continue
                if abs(player_a.rating - player_b.rating) > self.current_threshold:
                    continue

                player_ids = [player_a.player_id, player_b.player_id]
                if queue.claim_players(player_ids):
                    matches.append(Match.create(player_ids))
                    unavailable_players.update(player_ids)
                    break

                # Another worker claimed at least one member of this pair.
                unavailable_players.update(player_ids)
                break

        return matches

    def enforce_sla(self, queue: ClaimableQueue, now: datetime) -> List[Match]:
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        else:
            now = now.astimezone(timezone.utc)

        matches: List[Match] = []

        while True:
            entries = sorted(queue.get_entries(), key=lambda entry: entry.join_time)
            if len(entries) < 2:
                break

            oldest = entries[0]
            if (now - oldest.join_time).total_seconds() < self.max_wait_time:
                break

            partners = sorted(
                entries[1:],
                key=lambda entry: abs(entry.rating - oldest.rating),
            )

            claimed = False
            for partner in partners:
                player_ids = [oldest.player_id, partner.player_id]
                if queue.claim_players(player_ids):
                    matches.append(Match.create(player_ids))
                    claimed = True
                    break

            if not claimed:
                # The queue changed under this worker. Refresh before deciding.
                continue

        return matches
