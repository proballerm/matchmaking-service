from datetime import datetime, timezone
from typing import List

from core.models import QueueEntry


class MatchmakingQueue:
    """
    In-memory matchmaking queue.
    Stores players waiting to be matched.
    All timestamps are timezone-aware UTC.
    """

    def __init__(self):
        self._entries: List[QueueEntry] = []

    def add_player(self, player_id: str, rating: float, join_time: datetime) -> None:
        """
        Add a player to the queue.

        join_time MUST be timezone-aware UTC.
        The engine is responsible for supplying it.
        """
        if join_time.tzinfo is None:
            raise ValueError("join_time must be timezone-aware UTC")

        # Normalize to UTC defensively
        join_time = join_time.astimezone(timezone.utc)

        entry = QueueEntry(
            player_id=player_id,
            rating=rating,
            join_time=join_time,
        )
        self._entries.append(entry)

    def remove_players(self, player_ids: List[str]) -> None:
        """
        Remove players from the queue after they are matched or dequeued.
        """
        to_remove = set(player_ids)
        self._entries = [e for e in self._entries if e.player_id not in to_remove]

    def get_entries(self) -> List[QueueEntry]:
        """
        Return a copy of the current queue.
        """
        return list(self._entries)

    def size(self) -> int:
        return len(self._entries)
