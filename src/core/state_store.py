from __future__ import annotations

from typing import Dict, Protocol

from redis import Redis


ADAPT_THRESHOLD_SCRIPT = """
local current = tonumber(redis.call('HGET', KEYS[1], 'current_threshold') or ARGV[1])
local next_value = current + (tonumber(ARGV[2]) * (tonumber(ARGV[3]) - tonumber(ARGV[4])))
local minimum = tonumber(ARGV[5])
local maximum = tonumber(ARGV[6])
if next_value < minimum then next_value = minimum end
if next_value > maximum then next_value = maximum end
redis.call('HSET', KEYS[1], 'current_threshold', tostring(next_value))
return tostring(next_value)
"""


class StateStore(Protocol):
    def get_threshold(self) -> float: ...
    def adapt_threshold(self, avg_wait_time: float) -> float: ...
    def increment(self, field: str, amount: int = 1) -> None: ...
    def get_metrics(self) -> Dict[str, float]: ...


class InMemoryStateStore:
    def __init__(
        self,
        base_threshold: float = 100.0,
        min_threshold: float = 50.0,
        max_threshold: float = 400.0,
        target_avg_wait: float = 5.0,
        adapt_rate: float = 10.0,
    ) -> None:
        self.current_threshold = base_threshold
        self.min_threshold = min_threshold
        self.max_threshold = max_threshold
        self.target_avg_wait = target_avg_wait
        self.adapt_rate = adapt_rate
        self.counters = {
            "total_enqueues": 0.0,
            "total_matches": 0.0,
            "sla_forced_matches": 0.0,
        }

    def get_threshold(self) -> float:
        return float(self.current_threshold)

    def adapt_threshold(self, avg_wait_time: float) -> float:
        self.current_threshold += self.adapt_rate * (avg_wait_time - self.target_avg_wait)
        self.current_threshold = max(
            self.min_threshold,
            min(self.max_threshold, self.current_threshold),
        )
        return float(self.current_threshold)

    def increment(self, field: str, amount: int = 1) -> None:
        self.counters[field] = self.counters.get(field, 0.0) + float(amount)

    def get_metrics(self) -> Dict[str, float]:
        return dict(self.counters)


class RedisStateStore:
    def __init__(
        self,
        client: Redis,
        namespace: str = "matchmaking",
        base_threshold: float = 100.0,
        min_threshold: float = 50.0,
        max_threshold: float = 400.0,
        target_avg_wait: float = 5.0,
        adapt_rate: float = 10.0,
    ) -> None:
        self.client = client
        self.state_key = f"{namespace}:state"
        self.base_threshold = base_threshold
        self.min_threshold = min_threshold
        self.max_threshold = max_threshold
        self.target_avg_wait = target_avg_wait
        self.adapt_rate = adapt_rate
        self.client.hsetnx(self.state_key, "current_threshold", str(base_threshold))

    def get_threshold(self) -> float:
        value = self.client.hget(self.state_key, "current_threshold")
        return float(value if value is not None else self.base_threshold)

    def adapt_threshold(self, avg_wait_time: float) -> float:
        value = self.client.eval(
            ADAPT_THRESHOLD_SCRIPT,
            1,
            self.state_key,
            self.base_threshold,
            self.adapt_rate,
            avg_wait_time,
            self.target_avg_wait,
            self.min_threshold,
            self.max_threshold,
        )
        return float(value)

    def increment(self, field: str, amount: int = 1) -> None:
        self.client.hincrby(self.state_key, field, amount)

    def get_metrics(self) -> Dict[str, float]:
        values = self.client.hmget(
            self.state_key,
            ["total_enqueues", "total_matches", "sla_forced_matches"],
        )
        return {
            "total_enqueues": float(values[0] or 0),
            "total_matches": float(values[1] or 0),
            "sla_forced_matches": float(values[2] or 0),
        }
