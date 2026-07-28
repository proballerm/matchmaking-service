from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List

from redis import Redis

from core.models import QueueEntry


class RedisMatchmakingQueue:
    """Redis-backed matchmaking queue shared across service instances.

    A sorted set stores players by join time and a hash stores each player's
    rating. Queue mutations use Redis pipelines so related updates are applied
    together.
    """

    def __init__(self, client: Redis, namespace: str = "matchmaking") -> None:
        self.client = client
        self.queue_key = f"{namespace}:queue"
        self.ratings_key = f"{namespace}:ratings"

    @classmethod
    def from_url(cls, redis_url: str, namespace: str = "matchmaking") -> "RedisMatchmakingQueue":
        client = Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        return cls(client, namespace)

    def add_player(self, player_id: str, rating: float, join_time: datetime) -> None:
        if join_time.tzinfo is None:
            raise ValueError("join_time must be timezone-aware UTC")

        join_time = join_time.astimezone(timezone.utc)
        score = join_time.timestamp()

        with self.client.pipeline(transaction=True) as pipe:
            pipe.zadd(self.queue_key, {player_id: score}, nx=True)
            pipe.hsetnx(self.ratings_key, player_id, str(float(rating)))
            added, _ = pipe.execute()

        if added == 0:
            raise ValueError(f"player already queued: {player_id}")

    def remove_players(self, player_ids: Iterable[str]) -> None:
        ids = list(player_ids)
        if not ids:
            return

        with self.client.pipeline(transaction=True) as pipe:
            pipe.zrem(self.queue_key, *ids)
            pipe.hdel(self.ratings_key, *ids)
            pipe.execute()

    def get_entries(self) -> List[QueueEntry]:
        queued = self.client.zrange(self.queue_key, 0, -1, withscores=True)
        if not queued:
            return []

        player_ids = [player_id for player_id, _ in queued]
        ratings = self.client.hmget(self.ratings_key, player_ids)

        entries: List[QueueEntry] = []
        stale_ids: List[str] = []
        for (player_id, joined_at), rating in zip(queued, ratings):
            if rating is None:
                stale_ids.append(player_id)
                continue
            entries.append(
                QueueEntry(
                    player_id=player_id,
                    rating=float(rating),
                    join_time=datetime.fromtimestamp(float(joined_at), tz=timezone.utc),
                )
            )

        if stale_ids:
            self.client.zrem(self.queue_key, *stale_ids)

        return entries

    def size(self) -> int:
        return int(self.client.zcard(self.queue_key))

    def contains(self, player_id: str) -> bool:
        return self.client.zscore(self.queue_key, player_id) is not None

    def clear(self) -> None:
        self.client.delete(self.queue_key, self.ratings_key)
