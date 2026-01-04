from typing import Tuple
from math import pow
from core.models import Player


DEFAULT_K_FACTOR = 32


def expected_score(player_a: Player, player_b: Player) -> float:
    """
    Compute the expected score (win probability) for player A against player B.
    """
    return 1.0 / (1.0 + pow(10, (player_b.rating - player_a.rating) / 400))


def update_ratings(
    player_a: Player,
    player_b: Player,
    result_a: float,
    k_factor: int = DEFAULT_K_FACTOR
) -> Tuple[float, float]:
    """
    Update ratings for two players after a match.

    result_a:
        1.0 -> player A wins
        0.0 -> player A loses
        0.5 -> draw
    """

    expected_a = expected_score(player_a, player_b)
    expected_b = 1.0 - expected_a

    new_rating_a = player_a.rating + k_factor * (result_a - expected_a)
    new_rating_b = player_b.rating + k_factor * ((1.0 - result_a) - expected_b)

    return new_rating_a, new_rating_b
