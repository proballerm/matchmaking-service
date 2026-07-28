from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import Dict, List, Protocol

from redis import Redis

from core.models import MatchRecord


ATOMIC_CLAIM_AND_PUBLISH_SCRIPT = """
if redis.call('ZSCORE', KEYS[1], ARGV[1]) == false then
    return 0
end
if redis.call('ZSCORE', KEYS[1], ARGV[2]) == false then
    return 0
end

redis.call('ZREM', KEYS[1], ARGV[1], ARGV[2])
redis.call('HDEL', KEYS[2], ARGV[1], ARGV[2])
redis.call('HSET', KEYS[3], ARGV[3], ARGV[4])
redis.call('RPUSH', KEYS[4], ARGV[3])
redis.call('RPUSH', KEYS[5], ARGV[3])
return 1
"""


class MatchStore(Protocol):
    def publish(self, match: MatchRecord) -> None: ...
    def claim_and_publish(self, queue: object, match: MatchRecord) -> bool: ...
    def get_pending(self, player_id: str) -> List[MatchRecord]: ...
    def acknowledge(self, player_id: str, match_id: str) -> bool: ...


def _serialize(match: MatchRecord) -> str:
    payload = asdict(match)
    payload["player_ids"] = list(match.player_ids)
    payload["created_at"] = match.created_at.isoformat()
    return json.dumps(payload, separators=(",", ":"))


def _deserialize(payload: str) -> MatchRecord:
    data = json.loads(payload)
    return MatchRecord(
        match_id=data["match_id"],
        player_ids=tuple(data["player_ids"]),
        created_at=datetime.fromisoformat(data["created_at"]),
        rating_diff=float(data["rating_diff"]),
        sla_forced=bool(data["sla_forced"]),
        threshold_at_match=float(data["threshold_at_match"]),
    )


class InMemoryMatchStore:
    def __init__(self) -> None:
        self._matches: Dict[str, MatchRecord] = {}
        self._inboxes: Dict[str, List[str]] = {}

    def publish(self, match: MatchRecord) -> None:
        self._matches[match.match_id] = match
        for player_id in match.player_ids:
            self._inboxes.setdefault(player_id, []).append(match.match_id)

    def claim_and_publish(self, queue: object, match: MatchRecord) -> bool:
        claim_players = getattr(queue, "claim_players")
        if not claim_players(match.player_ids):
            return False
        self.publish(match)
        return True

    def get_pending(self, player_id: str) -> List[MatchRecord]:
        return [
            self._matches[match_id]
            for match_id in self._inboxes.get(player_id, [])
            if match_id in self._matches
        ]

    def acknowledge(self, player_id: str, match_id: str) -> bool:
        inbox = self._inboxes.get(player_id, [])
        if match_id not in inbox:
            return False
        inbox.remove(match_id)
        return True


class RedisMatchStore:
    """Durable per-player match inboxes backed by Redis."""

    def __init__(self, client: Redis, namespace: str = "matchmaking") -> None:
        self.client = client
        self.matches_key = f"{namespace}:matches"
        self.inbox_prefix = f"{namespace}:player_matches:"

    def _inbox_key(self, player_id: str) -> str:
        return f"{self.inbox_prefix}{player_id}"

    def publish(self, match: MatchRecord) -> None:
        payload = _serialize(match)
        with self.client.pipeline(transaction=True) as pipe:
            pipe.hset(self.matches_key, match.match_id, payload)
            for player_id in match.player_ids:
                pipe.rpush(self._inbox_key(player_id), match.match_id)
            pipe.execute()

    def claim_and_publish(self, queue: object, match: MatchRecord) -> bool:
        """Atomically claim a pair and publish the result to both inboxes."""
        if len(match.player_ids) != 2:
            raise ValueError("atomic delivery currently requires exactly two players")

        queue_client = getattr(queue, "client", None)
        queue_key = getattr(queue, "queue_key", None)
        ratings_key = getattr(queue, "ratings_key", None)
        if queue_client is not self.client or not queue_key or not ratings_key:
            raise ValueError("Redis queue and match store must share the same client")

        player_a, player_b = match.player_ids
        result = self.client.eval(
            ATOMIC_CLAIM_AND_PUBLISH_SCRIPT,
            5,
            queue_key,
            ratings_key,
            self.matches_key,
            self._inbox_key(player_a),
            self._inbox_key(player_b),
            player_a,
            player_b,
            match.match_id,
            _serialize(match),
        )
        return bool(result)

    def get_pending(self, player_id: str) -> List[MatchRecord]:
        match_ids = self.client.lrange(self._inbox_key(player_id), 0, -1)
        if not match_ids:
            return []

        payloads = self.client.hmget(self.matches_key, match_ids)
        pending: List[MatchRecord] = []
        stale_ids: List[str] = []
        for match_id, payload in zip(match_ids, payloads):
            if payload is None:
                stale_ids.append(match_id)
                continue
            pending.append(_deserialize(payload))

        if stale_ids:
            with self.client.pipeline(transaction=True) as pipe:
                for match_id in stale_ids:
                    pipe.lrem(self._inbox_key(player_id), 0, match_id)
                pipe.execute()

        return pending

    def acknowledge(self, player_id: str, match_id: str) -> bool:
        removed = self.client.lrem(self._inbox_key(player_id), 0, match_id)
        return bool(removed)
