from __future__ import annotations

import os
import random
import uuid

from locust import HttpUser, between, events, task


RATING_MIN = int(os.getenv("LOADTEST_RATING_MIN", "800"))
RATING_MAX = int(os.getenv("LOADTEST_RATING_MAX", "1800"))
POLL_ATTEMPTS = int(os.getenv("LOADTEST_POLL_ATTEMPTS", "8"))


class MatchmakingUser(HttpUser):
    """Simulates one player joining, polling, acknowledging, and rejoining."""

    wait_time = between(0.05, 0.25)

    def on_start(self) -> None:
        self.player_id = f"load-{uuid.uuid4()}"
        self.rating = random.randint(RATING_MIN, RATING_MAX)
        self.queued = False
        self.enqueue_player()

    def enqueue_player(self) -> None:
        with self.client.post(
            "/enqueue",
            json={"player_id": self.player_id, "rating": self.rating},
            name="POST /enqueue",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                self.queued = True
                response.success()
            elif response.status_code == 409:
                self.queued = True
                response.success()
            else:
                response.failure(f"enqueue failed: {response.status_code}")

    @task(8)
    def poll_for_match(self) -> None:
        if not self.queued:
            self.enqueue_player()
            return

        with self.client.get(
            f"/players/{self.player_id}/matches",
            name="GET /players/:id/matches",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"poll failed: {response.status_code}")
                return

            payload = response.json()
            matches = payload.get("matches", [])
            response.success()

        if not matches:
            return

        for match in matches:
            match_id = match["match_id"]
            with self.client.post(
                f"/players/{self.player_id}/matches/ack",
                json={"match_id": match_id},
                name="POST /players/:id/matches/ack",
                catch_response=True,
            ) as ack_response:
                if ack_response.status_code == 200:
                    ack_response.success()
                else:
                    ack_response.failure(
                        f"ack failed: {ack_response.status_code}"
                    )

        self.queued = False
        self.player_id = f"load-{uuid.uuid4()}"
        self.rating = random.randint(RATING_MIN, RATING_MAX)
        self.enqueue_player()

    @task(1)
    def read_metrics(self) -> None:
        self.client.get("/metrics", name="GET /metrics")


@events.test_stop.add_listener
def validate_matchmaking(environment, **_kwargs) -> None:
    """Fail the run when the aggregate error rate exceeds the configured SLO."""
    threshold = float(os.getenv("LOADTEST_MAX_FAILURE_RATE", "0.01"))
    stats = environment.runner.stats.total
    failure_rate = stats.fail_ratio if stats.num_requests else 0.0
    if failure_rate > threshold:
        environment.process_exit_code = 1
