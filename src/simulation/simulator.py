from datetime import datetime, timedelta
from typing import Dict, List

from core.models import Player
from core.queue import MatchmakingQueue
from core.matcher import Matchmaker
from core.rating import update_ratings
from simulation.generators import player_stream


class MatchmakingSimulator:
    """
    Simulation harness with adaptive matchmaking and SLA enforcement.
    """

    def __init__(
        self,
        arrival_rate_per_second: float,
        simulation_duration_seconds: int,
    ):
        self.arrival_rate = arrival_rate_per_second
        self.duration = simulation_duration_seconds

        self.players: Dict[str, Player] = {}
        self.queue = MatchmakingQueue()
        self.matchmaker = Matchmaker()

        # Metrics
        self.wait_times: List[float] = []
        self.normal_wait_times: List[float] = []
        self.sla_wait_times: List[float] = []
        self.rating_diffs: List[float] = []
        self.threshold_history: List[float] = []

        self.join_times: Dict[str, datetime] = {}
        self.sla_forced_matches = 0

    def run(self) -> None:
        start_time = datetime.utcnow()
        current_time = start_time
        end_time = start_time + timedelta(seconds=self.duration)

        arrivals = list(
            player_stream(
                start_time=start_time,
                rate_per_second=self.arrival_rate,
                duration_seconds=self.duration,
            )
        )
        arrival_index = 0

        while current_time < end_time:
            # Handle arrivals
            while (
                arrival_index < len(arrivals)
                and arrivals[arrival_index][1] <= current_time
            ):
                pid, arrival_time, rating = arrivals[arrival_index]
                self.players[pid] = Player(pid, rating, arrival_time)
                self.queue.add_player(pid, rating)
                self.join_times[pid] = arrival_time
                arrival_index += 1

            # Normal matches
            normal_matches = self.matchmaker.try_form_matches(self.queue)

            # SLA matches
            sla_matches = self.matchmaker.enforce_sla(self.queue, current_time)
            self.sla_forced_matches += len(sla_matches)

            # Process normal matches
            for match in normal_matches:
                p1_id, p2_id = match.player_ids

                w1 = (current_time - self.join_times[p1_id]).total_seconds()
                w2 = (current_time - self.join_times[p2_id]).total_seconds()

                self.normal_wait_times.extend([w1, w2])
                self.wait_times.extend([w1, w2])

                p1 = self.players[p1_id]
                p2 = self.players[p2_id]
                self.rating_diffs.append(abs(p1.rating - p2.rating))

                result = 1.0 if p1.rating >= p2.rating else 0.0
                p1.rating, p2.rating = update_ratings(p1, p2, result)

            # Process SLA matches
            for match in sla_matches:
                p1_id, p2_id = match.player_ids

                w1 = (current_time - self.join_times[p1_id]).total_seconds()
                w2 = (current_time - self.join_times[p2_id]).total_seconds()

                self.sla_wait_times.extend([w1, w2])
                self.wait_times.extend([w1, w2])

                p1 = self.players[p1_id]
                p2 = self.players[p2_id]
                self.rating_diffs.append(abs(p1.rating - p2.rating))

                result = 1.0 if p1.rating >= p2.rating else 0.0
                p1.rating, p2.rating = update_ratings(p1, p2, result)

            # Adaptive threshold (IMPORTANT FIX)
            if len(self.normal_wait_times) >= 10:
                recent = self.normal_wait_times[-10:]
                avg_wait = sum(recent) / len(recent)
                self.matchmaker.adapt_threshold(avg_wait)

            self.threshold_history.append(self.matchmaker.current_threshold)
            current_time += timedelta(seconds=1)

    def summary(self) -> dict:
        matches_formed = len(self.wait_times) // 2

        return {
            "players_created": len(self.players),
            "matches_formed": matches_formed,
            "avg_wait_time": sum(self.wait_times) / len(self.wait_times)
            if self.wait_times else 0,
            "avg_rating_diff": sum(self.rating_diffs) / len(self.rating_diffs)
            if self.rating_diffs else 0,
            "final_threshold": self.matchmaker.current_threshold,
            "sla_forced_matches": self.sla_forced_matches,
            "sla_forced_percentage": (
                100 * self.sla_forced_matches / matches_formed
                if matches_formed else 0
            ),
        }
