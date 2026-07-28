from datetime import datetime, timezone
from typing import Iterable, List

from core.models import QueueEntry


class MatchmakingQueue:
    """In-memory matchmaking queue used by tests and single-process runs."""

    def __init__(self):
        self._entries: List[QueueEntry] = []

    def add_player(self, player_id: str, rating: float, join_time: datetime) -> None:
        if join_time.tzinfo is None:
            raise ValueError("join_time must be timezone-aware UTC")

        if any(entry.player_id == player_id for entry in self._entries):
            raise ValueError(f"player already queued: {player_id}")

        self._entries.append(
            QueueEntry(
                player_id=player_id,
                rating=rating,
                join_time=join_time.astimezone(timezone.utc),
            )
        )

    def remove_players(self, player_ids: Iterable[str]) -> None:
        to_remove = set(player_ids)
        self._entries = [entry for entry in self._entries if entry.player_id not in to_remove]

    def claim_players(self, player_ids: Iterable[str]) -> bool:
        """Remove every requested player only when all are still queued.

        This mirrors the atomic contract implemented by Redis. The in-memory
        backend is protected by the API's process-local lock.
        """
        ids = list(dict.fromkeys(player_ids))
        if not ids:
            return False

        queued_ids = {entry.player_id for entry in self._entries}
        if not all(player_id in queued_ids for player_id in ids):
            return False

        self.remove_players(ids)
        return True

    def get_entries(self) -> List[QueueEntry]:
        return list(self._entries)

    def size(self) -> int:
        return len(self._entries)
