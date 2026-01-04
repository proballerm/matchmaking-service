from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from core.matcher import Matchmaker
from core.models import Match, Player
from core.queue import MatchmakingQueue


@dataclass
class MatchRecord:
    match_id: str
    player_ids: Tuple[str, str]
    created_at: datetime
    rating_diff: float
    sla_forced: bool
    threshold_at_match: float


class MatchmakingEngine:
    """
    Engine layer: the service core API that a web server can call.

    Responsibilities:
    Accept enqueue requests
    Run matchmaking once (normal plus SLA)
    Persist created matches in memory
    Expose queue state plus metrics
    """

    def __init__(
        self,
        matchmaker: Optional[Matchmaker] = None,
        now_fn: Optional[Callable[[], datetime]] = None,
    ):
        self.queue = MatchmakingQueue()
        self.matchmaker = matchmaker or Matchmaker()

        # Deterministic clock injection for tests
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

        p = Player(player_id, rating, now)
        self.players[player_id] = p
        self.join_times[player_id] = now

        # Queue never generates time; engine supplies timezone-aware UTC join time.
        self.queue.add_player(player_id, rating, now)

        self.total_enqueues += 1
        return True

    def dequeue_player(self, player_id: str) -> bool:
        """
        Cancel matchmaking for a player.
        Returns True if the player existed and was removed, else False.
        """
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

        # Adaptive threshold should only consider normal matches.
        if normal_matches:
            waits: List[float] = []
            for m in normal_matches:
                for pid in m.player_ids:
                    jt = self.join_times.get(pid)
                    if jt is not None:
                        waits.append((now - jt).total_seconds())

            if waits:
                avg_wait = sum(waits) / len(waits)
                self.matchmaker.adapt_threshold(avg_wait)

        self.sla_forced_matches += len(sla_matches)

        for m in normal_matches:
            rec = self._record_match(m, now, sla_forced=False)
            new_records.append(rec)

        for m in sla_matches:
            rec = self._record_match(m, now, sla_forced=True)
            new_records.append(rec)

        self.created_matches.extend(new_records)
        self.total_matches += len(new_records)

        return new_records

    def get_and_clear_matches(self) -> List[MatchRecord]:
        out = self.created_matches
        self.created_matches = []
        return out

    def get_metrics(self) -> Dict[str, float]:
        queue_depth = len(self.queue.get_entries())
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

        rating_diff = abs(p1.rating - p2.rating)
        match_id = str(uuid4())

        return MatchRecord(
            match_id=match_id,
            player_ids=(p1_id, p2_id),
            created_at=now,
            rating_diff=rating_diff,
            sla_forced=sla_forced,
            threshold_at_match=float(self.matchmaker.current_threshold),
        )
