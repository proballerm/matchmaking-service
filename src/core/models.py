from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Tuple
import uuid


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Player:
    """Represents a player in the matchmaking system."""

    player_id: str
    rating: float = 1000.0
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class QueueEntry:
    """Represents a player waiting in the matchmaking queue."""

    player_id: str
    rating: float
    join_time: datetime


@dataclass
class Match:
    """Represents a completed match selected by the matcher."""

    match_id: str
    player_ids: List[str]
    created_at: datetime = field(default_factory=utcnow)

    @staticmethod
    def create(player_ids: List[str]) -> "Match":
        return Match(
            match_id=str(uuid.uuid4()),
            player_ids=player_ids,
            created_at=utcnow(),
        )


@dataclass
class MatchRecord:
    """Serializable match result delivered to each participating player."""

    match_id: str
    player_ids: Tuple[str, str]
    created_at: datetime
    rating_diff: float
    sla_forced: bool
    threshold_at_match: float
