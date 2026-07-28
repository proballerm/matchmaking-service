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
- Prometheus instrumentation and a provisioned Grafana dashboard
- Reproducible Locust load tests with CSV, HTML, and JSON results
- In-memory backends for local development and deterministic tests

## Architecture

```text
Clients / Locust
       |
FastAPI instances / matchmaking workers
       |
Shared Redis queue, inboxes, threshold, and counters
       |
Prometheus  <---- /prometheus
       |
Grafana dashboard
```

Redis stores waiting players, durable match inboxes, the adaptive threshold, and system-wide counters. Lua scripts make player claiming, match publication, threshold adaptation, acknowledgement, and cleanup atomic.

Key files:

- `src/core/engine.py` — orchestration and matchmaking lifecycle
- `src/core/match_store.py` — atomic publication, acknowledgement, and cleanup
- `src/core/state_store.py` — shared threshold and global counters
- `src/api/observability.py` — Prometheus collector and HTTP middleware
- `loadtest/locustfile.py` — realistic join, poll, acknowledge, and rejoin workload
- `loadtest/run_benchmark.sh` — reproducible headless benchmark runner
- `loadtest/summarize_results.py` — normalized JSON result generator
- `benchmark/REPORT.md` — evidence-based benchmark report template

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

## Run a benchmark

Install development dependencies and start the full stack:

```bash
pip install -e ".[dev]"
docker compose up --build
```

Run the default 200-user, two-minute scenario:

```bash
bash loadtest/run_benchmark.sh
```

Override the workload through environment variables:

```bash
USERS=500 SPAWN_RATE=50 RUN_TIME=5m bash loadtest/run_benchmark.sh
```

The simulated player lifecycle is:

1. Enqueue with a randomized rating.
2. Poll the player's durable match inbox.
3. Acknowledge a delivered match.
4. Rejoin with a new player ID.
5. Periodically read system metrics.

Generated artifacts are written under `benchmark/results/`:

```text
*_stats.csv
*_failures.csv
*_exceptions.csv
*.html
*_summary.json
```

The JSON summary includes requests per second, failure rate, median latency, average latency, p95, and p99. The Locust run exits unsuccessfully when the aggregate failure rate exceeds `LOADTEST_MAX_FAILURE_RATE`, which defaults to `0.01`.

Example custom guardrail:

```bash
LOADTEST_MAX_FAILURE_RATE=0.005 USERS=300 RUN_TIME=3m bash loadtest/run_benchmark.sh
```

Do not claim benchmark numbers until a real run is completed on documented hardware. Copy verified values into `benchmark/REPORT.md` and record the commit, API worker count, CPU, memory, and Redis deployment.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | unset | Redis connection URL. When unset, the service uses memory. |
| `REDIS_NAMESPACE` | `matchmaking` | Prefix for queue, delivery, threshold, and metric keys. |
| `ENABLE_BACKGROUND_TICK` | `1` | Enables the background matchmaking loop. |
| `TICK_INTERVAL_SECONDS` | `1.0` | Seconds between matchmaking ticks. |
| `LOADTEST_RATING_MIN` | `800` | Minimum simulated player rating. |
| `LOADTEST_RATING_MAX` | `1800` | Maximum simulated player rating. |
| `LOADTEST_MAX_FAILURE_RATE` | `0.01` | Maximum accepted aggregate request failure ratio. |

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

## Tests

```bash
pytest -q
```

The suite covers multi-worker atomicity, durable delivery, shared threshold state, cleanup, Prometheus collection, HTTP instrumentation, and benchmark-result parsing.

## Current limitations

- Match records are removed after delivery, so long-term history requires a separate database.
- HTTP metrics are process-local when running multiple Uvicorn workers; Prometheus aggregates them across scrape targets.
- Published benchmark numbers still require a real run on documented hardware.
- The adaptive controller still needs tuning with realistic production load data.

## Next improvements

- Execute and publish benchmark results from controlled hardware
- Add PostgreSQL-backed long-term match history
- Add alerting rules for queue growth, latency, and SLA degradation
- Add authentication and rate limiting
- Add GitHub Actions CI for tests and benchmark smoke checks
