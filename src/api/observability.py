from __future__ import annotations

import time
from typing import Callable

from fastapi import FastAPI, Request
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest
from prometheus_client.core import GaugeMetricFamily
from starlette.responses import Response


class MatchmakingCollector:
    """Collect shared matchmaking state at scrape time."""

    def __init__(self, metrics_fn: Callable[[], dict[str, float]]) -> None:
        self.metrics_fn = metrics_fn

    def collect(self):
        metrics = self.metrics_fn()
        definitions = {
            "queue_depth": "Players currently waiting in the matchmaking queue",
            "total_enqueues": "Players successfully added to the queue",
            "total_matches": "Matches successfully created",
            "sla_forced_matches": "Matches forced by the maximum-wait SLA",
            "sla_forced_percentage": "Percentage of matches forced by the SLA",
            "current_threshold": "Current allowed rating difference",
        }
        for key, description in definitions.items():
            gauge = GaugeMetricFamily(f"matchmaking_{key}", description)
            gauge.add_metric([], float(metrics.get(key, 0.0)))
            yield gauge


def install_observability(app: FastAPI, metrics_fn: Callable[[], dict[str, float]]) -> None:
    registry = CollectorRegistry()
    registry.register(MatchmakingCollector(metrics_fn))

    request_count = Counter(
        "matchmaking_http_requests_total",
        "HTTP requests handled by the API process",
        ["method", "route", "status"],
        registry=registry,
    )
    request_duration = Histogram(
        "matchmaking_http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "route"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
        registry=registry,
    )

    @app.middleware("http")
    async def observe_request(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        request_count.labels(
            method=request.method,
            route=route_path,
            status=str(response.status_code),
        ).inc()
        request_duration.labels(method=request.method, route=route_path).observe(
            time.perf_counter() - started
        )
        return response

    @app.get("/prometheus", include_in_schema=False)
    async def prometheus_metrics() -> Response:
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
