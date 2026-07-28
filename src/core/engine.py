from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Protocol, Tuple
from uuid import uuid4

from core.matcher import Matchmaker
from core.models import Match, Player, QueueEntry
from core.queue import MatchmakingQueue


class QueueBackend(Protocol):
    def add_player(self, player_id: str, rating: float, join_time: datetime) -> None: ...
    def remove_players(self, player_ids: List[str]) -> None: ...
    def get_entries(self) -> List[QueueEntry]: ...
    def size(self) -> int: ...


@dataclass
class MatchRecord:
    match_id: str
    player_ids: Tuple[str, str]
    created_at: datetime
    rating_diff: float
    sla_forced: bool
    threshold_at_match: float


class MatchmakingEngine:
    """Framework-independent matchmaking engine."""

    def __init__(
        self,
        matchmaker: Optional[Matchmaker] = None,
        now_fn: Optional[Callable[[], datetime]] = None,
        queue: Optional[QueueBackend] = None,
    ):
        self.queue: QueueBackend = queue or MatchmakingQueue()
        self.matchmaker = matchmaker or Matchmaker()
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))

        self.players: Dict[str, Player] = {}
        self.join_times: Dict[str, datetime] = {}
        self.created_matches: List[MatchRecord] = []

        self.total_enqueues = 0
        self.total_matches = 0
        self.sla_forced_matches = 0

    def enqueue_player(
        self,
        player_id: str,
        rating: float,
        now: Optional[datetime] = None,
    ) -> bool:
        now = now or self._now_fn()

        if player_id in self.join_times:
            return False

        try:
            self.queue.add_player(player_id, rating, now)
        except ValueError:
            return False

        self.players[player_id] = Player(player_id, rating, now)
        self.join_times[player_id] = now
        self.total_enqueues += 1
        return True

    def dequeue_player(self, player_id: str) -> bool:
        if player_id not in self.join_times:
            return False

        self.queue.remove_players([player_id])
        self.join_times.pop(player_id, None)
        self.players.pop(player_id, None)
        return True

    def run_matchmaking_once(self, now: Optional[datetime] = None) -> List[MatchRecord]:
        now = now or self._now_fn()
        new_records: List[MatchRecord] = []

        normal_matches = self.matchmaker.try_form_matches(self.queue)
        sla_matches = self.matchmaker.enforce_sla(self.queue, now)

        if normal_matches:
            waits: List[float] = []
            for match in normal_matches:
                for player_id in match.player_ids:
                    joined_at = self.join_times.get(player_id)
                    if joined_at is not None:
                        waits.append((now - joined_at).total_seconds())

            if waits:
                self.matchmaker.adapt_threshold(sum(waits) / len(waits))

        self.sla_forced_matches += len(sla_matches)

        for match in normal_matches:
            new_records.append(self._record_match(match, now, sla_forced=False))

        for match in sla_matches:
            new_records.append(self._record_match(match, now, sla_forced=True))

        self.created_matches.extend(new_records)
        self.total_matches += len(new_records)
        return new_records

    def get_and_clear_matches(self) -> List[MatchRecord]:
        out = self.created_matches
        self.created_matches = []
        return out

    def get_metrics(self) -> Dict[str, float]:
        queue_depth = self.queue.size()
        sla_pct = (self.sla_forced_matches / self.total_matches) * 100 if self.total_matches else 0.0

        return {
            "queue_depth": float(queue_depth),
            "total_enqueues": float(self.total_enqueues),
            "total_matches": float(self.total_matches),
            "sla_forced_matches": float(self.sla_forced_matches),
            "sla_forced_percentage": float(sla_pct),
            "current_threshold": float(self.matchmaker.current_threshold),
        }

    def _record_match(self, match: Match, now: datetime, sla_forced: bool) -> MatchRecord:
        p1_id, p2_id = match.player_ids
        p1 = self.players[p1_id]
        p2 = self.players[p2_id]

        return MatchRecord(
            match_id=str(uuid4()),
            player_ids=(p1_id, p2_id),
            created_at=now,
            rating_diff=abs(p1.rating - p2.rating),
            sla_forced=sla_forced,
            threshold_at_match=float(self.matchmaker.current_threshold),
        )
