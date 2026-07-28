from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional, Protocol
from uuid import uuid4

from core.match_store import InMemoryMatchStore, MatchStore
from core.matcher import Matchmaker
from core.models import MatchRecord, Player, QueueEntry
from core.queue import MatchmakingQueue
from core.state_store import InMemoryStateStore, StateStore


class QueueBackend(Protocol):
    def add_player(self, player_id: str, rating: float, join_time: datetime) -> None: ...
    def remove_players(self, player_ids: Iterable[str]) -> None: ...
    def claim_players(self, player_ids: Iterable[str]) -> bool: ...
    def get_entries(self) -> List[QueueEntry]: ...
    def size(self) -> int: ...


class MatchmakingEngine:
    """Framework-independent matchmaking engine."""

    def __init__(
        self,
        matchmaker: Optional[Matchmaker] = None,
        now_fn: Optional[Callable[[], datetime]] = None,
        queue: Optional[QueueBackend] = None,
        match_store: Optional[MatchStore] = None,
        state_store: Optional[StateStore] = None,
    ):
        self.queue: QueueBackend = queue or MatchmakingQueue()
        self.match_store: MatchStore = match_store or InMemoryMatchStore()
        self.matchmaker = matchmaker or Matchmaker()
        self.state_store: StateStore = state_store or InMemoryStateStore(
            base_threshold=self.matchmaker.base_threshold,
            min_threshold=self.matchmaker.min_threshold,
            max_threshold=self.matchmaker.max_threshold,
            target_avg_wait=self.matchmaker.target_avg_wait,
            adapt_rate=self.matchmaker.adapt_rate,
        )
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))

        self.players: Dict[str, Player] = {}
        self.join_times: Dict[str, datetime] = {}
        self._sync_waiting_players()
        self.created_matches: List[MatchRecord] = []

    def _sync_waiting_players(self) -> None:
        entries = self.queue.get_entries()
        self.players = {
            entry.player_id: Player(entry.player_id, entry.rating, entry.join_time)
            for entry in entries
        }
        self.join_times = {
            entry.player_id: entry.join_time for entry in entries
        }

    def enqueue_player(
        self,
        player_id: str,
        rating: float,
        now: Optional[datetime] = None,
    ) -> bool:
        now = now or self._now_fn()
        try:
            self.queue.add_player(player_id, rating, now)
        except ValueError:
            return False

        self.players[player_id] = Player(player_id, rating, now)
        self.join_times[player_id] = now
        self.state_store.increment("total_enqueues")
        return True

    def dequeue_player(self, player_id: str) -> bool:
        self._sync_waiting_players()
        if player_id not in self.join_times:
            return False

        self.queue.remove_players([player_id])
        self.join_times.pop(player_id, None)
        self.players.pop(player_id, None)
        return True

    def run_matchmaking_once(self, now: Optional[datetime] = None) -> List[MatchRecord]:
        now = now or self._now_fn()
        self._sync_waiting_players()
        self.matchmaker.current_threshold = self.state_store.get_threshold()
        new_records: List[MatchRecord] = []
        normal_waits: List[float] = []

        def claim_normal(player_ids: List[str], rating_diff: float) -> bool:
            record = self._build_match_record(
                player_ids,
                now,
                rating_diff,
                sla_forced=False,
            )
            if not self.match_store.claim_and_publish(self.queue, record):
                return False

            for player_id in player_ids:
                joined_at = self.join_times.get(player_id)
                if joined_at is not None:
                    normal_waits.append((now - joined_at).total_seconds())

            new_records.append(record)
            self._remove_local_players(player_ids)
            return True

        normal_matches = self.matchmaker.try_form_matches(
            self.queue,
            claim_match=claim_normal,
        )

        if normal_matches and normal_waits:
            self.matchmaker.current_threshold = self.state_store.adapt_threshold(
                sum(normal_waits) / len(normal_waits)
            )

        def claim_sla(player_ids: List[str], rating_diff: float) -> bool:
            record = self._build_match_record(
                player_ids,
                now,
                rating_diff,
                sla_forced=True,
            )
            if not self.match_store.claim_and_publish(self.queue, record):
                return False
            new_records.append(record)
            self._remove_local_players(player_ids)
            return True

        sla_matches = self.matchmaker.enforce_sla(
            self.queue,
            now,
            claim_match=claim_sla,
        )

        if new_records:
            self.state_store.increment("total_matches", len(new_records))
        if sla_matches:
            self.state_store.increment("sla_forced_matches", len(sla_matches))

        self.created_matches.extend(new_records)
        return new_records

    def get_pending_matches(self, player_id: str) -> List[MatchRecord]:
        return self.match_store.get_pending(player_id)

    def acknowledge_match(self, player_id: str, match_id: str) -> bool:
        return self.match_store.acknowledge(player_id, match_id)

    def get_and_clear_matches(self) -> List[MatchRecord]:
        out = self.created_matches
        self.created_matches = []
        return out

    def get_metrics(self) -> Dict[str, float]:
        metrics = self.state_store.get_metrics()
        total_matches = metrics["total_matches"]
        sla_matches = metrics["sla_forced_matches"]
        metrics.update(
            {
                "queue_depth": float(self.queue.size()),
                "sla_forced_percentage": (sla_matches / total_matches) * 100 if total_matches else 0.0,
                "current_threshold": float(self.state_store.get_threshold()),
            }
        )
        return metrics

    def _build_match_record(
        self,
        player_ids: List[str],
        now: datetime,
        rating_diff: float,
        sla_forced: bool,
    ) -> MatchRecord:
        return MatchRecord(
            match_id=str(uuid4()),
            player_ids=(player_ids[0], player_ids[1]),
            created_at=now,
            rating_diff=rating_diff,
            sla_forced=sla_forced,
            threshold_at_match=float(self.matchmaker.current_threshold),
        )

    def _remove_local_players(self, player_ids: Iterable[str]) -> None:
        for player_id in player_ids:
            self.players.pop(player_id, None)
            self.join_times.pop(player_id, None)
