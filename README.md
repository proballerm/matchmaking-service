# Matchmaking Service

A skill-based matchmaking backend built with FastAPI. The service balances match fairness and queue latency with an adaptive rating threshold while enforcing a hard maximum-wait SLA.

## Features

- Skill-based matching with adaptive rating thresholds
- SLA-forced matches for players waiting beyond the configured maximum
- Redis-backed queue persistence and restart recovery
- Atomic Redis match commits across concurrent workers
- Durable per-player match delivery and acknowledgement
- Automatic match cleanup after final acknowledgement
- Shared Redis-backed threshold and system-wide counters
- Prometheus API instrumentation and a provisioned Grafana dashboard
- In-memory backends for local development and deterministic tests
- Docker Compose development and observability stack

## Architecture

```text
Clients
   |
FastAPI instances / matchmaking workers
   |
Shared Redis queue, inboxes, threshold, and counters
   |
Prometheus  <---- /prometheus
   |
Grafana dashboard
```

The engine accepts queue, delivery, and state backends through small interfaces. Redis stores waiting players, durable match inboxes, the adaptive threshold, and system-wide counters. Lua scripts make player claiming, match publication, threshold adaptation, acknowledgement, and cleanup atomic.

Prometheus scrapes each API process for HTTP request metrics and reads shared matchmaking state at scrape time. This keeps queue depth, total matches, SLA rate, and threshold values consistent with Redis while still reporting process-level API latency and status codes.

Key files:

- `src/core/engine.py` — orchestration and matchmaking lifecycle
- `src/core/match_store.py` — atomic publication, acknowledgement, and cleanup
- `src/core/state_store.py` — shared threshold and global counters
- `src/api/observability.py` — Prometheus collector and HTTP middleware
- `observability/prometheus.yml` — scrape configuration
- `observability/grafana/` — provisioned datasource and dashboard

## Run the full stack

```bash
docker compose up --build
```

Open:

- API documentation: `http://localhost:8000/docs`
- JSON metrics: `http://localhost:8000/metrics`
- Prometheus metrics: `http://localhost:8000/prometheus`
- Prometheus UI: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Grafana development credentials:

```text
username: admin
password: admin
```

The **Matchmaking Service Overview** dashboard is provisioned automatically. It includes queue depth, rating threshold, total matches, SLA-forced percentage, match rate, API p95 latency, request rate, and 5xx error rate.

Multiple API processes can safely share Redis state:

```bash
REDIS_URL=redis://localhost:6379/0 uvicorn api.app:app --workers 4
```

## Run without Redis

```bash
pip install -e ".[dev]"
uvicorn api.app:app --reload
```

Without `REDIS_URL`, the service uses in-memory queue, match-store, and state-store implementations.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | unset | Redis connection URL. When unset, the service uses memory. |
| `REDIS_NAMESPACE` | `matchmaking` | Prefix for queue, delivery, threshold, and metric keys. |
| `ENABLE_BACKGROUND_TICK` | `1` | Enables the background matchmaking loop. |
| `TICK_INTERVAL_SECONDS` | `1.0` | Seconds between matchmaking ticks. |

## API

### Enqueue a player

```http
POST /enqueue
Content-Type: application/json

{
  "player_id": "p1",
  "rating": 1200
}
```

### Poll pending matches

```http
GET /players/p1/matches
```

### Acknowledge delivery

```http
POST /players/p1/matches/ack
Content-Type: application/json

{
  "match_id": "example-match-id"
}
```

### Read JSON metrics

```http
GET /metrics
```

### Scrape Prometheus metrics

```http
GET /prometheus
```

Exported series include:

```text
matchmaking_queue_depth
matchmaking_total_enqueues
matchmaking_total_matches
matchmaking_sla_forced_matches
matchmaking_sla_forced_percentage
matchmaking_current_threshold
matchmaking_http_requests_total
matchmaking_http_request_duration_seconds
```

## Tests

```bash
pytest -q
```

Redis tests use `fakeredis[lua]`, so a running Redis server is not required. The suite covers multi-worker atomicity, durable delivery, shared threshold state, cleanup, fresh scrape-time collection, and HTTP instrumentation.

## Current limitations

- Match records are removed after delivery, so long-term history requires a separate database.
- HTTP metrics are process-local when running multiple Uvicorn workers; Prometheus aggregates them across scrape targets.
- The adaptive controller still needs tuning with realistic production load data.

## Next improvements

- Add load testing and publish benchmark results
- Add PostgreSQL-backed long-term match history
- Add alerting rules for queue growth, latency, and SLA degradation
- Add authentication and rate limiting
