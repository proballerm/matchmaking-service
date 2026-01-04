from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List
import uuid


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Player:
    """
    Represents a player in the matchmaking system.
    """
    player_id: str
    rating: float = 1000.0
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class QueueEntry:
    """
    Represents a player waiting in the matchmaking queue.
    """
    player_id: str
    rating: float
    join_time: datetime


@dataclass
class Match:
    """
    Represents a completed match.
    """
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
