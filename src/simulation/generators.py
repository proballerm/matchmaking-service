import random
from typing import Iterator, Tuple
from datetime import datetime, timedelta


def poisson_arrivals(
    start_time: datetime,
    rate_per_second: float,
    duration_seconds: int,
) -> Iterator[datetime]:
    """
    Generate arrival timestamps using a Poisson process.

    rate_per_second: expected arrivals per second
    """
    current_time = start_time
    end_time = start_time + timedelta(seconds=duration_seconds)

    while current_time < end_time:
        # Exponential inter-arrival time
        wait_seconds = random.expovariate(rate_per_second)
        current_time += timedelta(seconds=wait_seconds)

        if current_time < end_time:
            yield current_time


def skill_distribution(
    mean: float = 1000.0,
    std_dev: float = 200.0,
    min_rating: float = 100.0,
    max_rating: float = 3000.0,
) -> float:
    """
    Sample a player's initial skill rating from a bounded normal distribution.
    """
    rating = random.gauss(mean, std_dev)
    return max(min_rating, min(max_rating, rating))


def player_stream(
    start_time: datetime,
    rate_per_second: float,
    duration_seconds: int,
    mean_rating: float = 1000.0,
    std_dev: float = 200.0,
) -> Iterator[Tuple[str, datetime, float]]:
    """
    Yield (player_id, arrival_time, initial_rating) tuples.
    """
    arrivals = poisson_arrivals(start_time, rate_per_second, duration_seconds)

    for idx, arrival_time in enumerate(arrivals):
        rating = skill_distribution(mean_rating, std_dev)
        yield f"P{idx}", arrival_time, rating
