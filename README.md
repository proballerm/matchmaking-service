# Matchmaking Service

A skill-based matchmaking backend built with FastAPI. The service balances match fairness and queue latency with an adaptive rating threshold while enforcing a hard maximum-wait SLA.

## Features

- Skill-based matching with adaptive rating thresholds
- SLA-forced matches for players waiting beyond the configured maximum
- Redis-backed queue persistence with automatic recovery after API restarts
- In-memory fallback for local development and deterministic tests
- Continuous background matchmaking loop
- Docker and Docker Compose support
- Metrics for queue depth, match count, threshold state, and SLA-forced matches

## Architecture

```text
Client
  |
FastAPI API + matchmaking engine
  |
Redis sorted-set queue
```

The engine is independent of FastAPI and accepts any queue backend matching the queue interface.

- `src/core/engine.py` — orchestration, metrics, and match records
- `src/core/matcher.py` — threshold matching and SLA enforcement
- `src/core/queue.py` — in-memory queue
- `src/core/redis_queue.py` — Redis sorted-set and rating-hash backend
- `src/api/app.py` — HTTP API and background worker

Redis stores player IDs in a sorted set scored by UTC join timestamp. Ratings are stored in a Redis hash. On startup, the engine reloads existing queue entries so waiting players survive an API restart.

> The current deployment model assumes one active matchmaking worker. Atomic multi-worker matching is a future enhancement.

## Run with Redis

The easiest setup uses Docker Compose:

```bash
docker compose up --build
```

Then open:

- API documentation: `http://localhost:8000/docs`
- Health endpoint: `http://localhost:8000/health`
- Metrics: `http://localhost:8000/metrics`

The health response reports whether the queue backend is `redis` or `memory`.

## Run without Redis

Install dependencies and start the API without setting `REDIS_URL`:

```bash
pip install -e ".[dev]"
uvicorn api.app:app --reload
```

The service will use the original in-memory queue.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | unset | Redis connection URL. When unset, the service uses memory. |
| `REDIS_NAMESPACE` | `matchmaking` | Prefix for Redis queue keys. |
| `ENABLE_BACKGROUND_TICK` | `1` | Enables the background matchmaking loop. |
| `TICK_INTERVAL_SECONDS` | `1.0` | Seconds between matchmaking ticks. |

Example:

```bash
REDIS_URL=redis://localhost:6379/0 uvicorn api.app:app --reload
```

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

Duplicate queued player IDs return HTTP `409`.

### Dequeue a player

```http
POST /dequeue
Content-Type: application/json

{
  "player_id": "p1"
}
```

### Poll matches

```http
GET /matches
```

### Trigger one matchmaking tick

```http
POST /tick
Content-Type: application/json

{}
```

### Read metrics

```http
GET /metrics
```

## Tests

```bash
pytest -q
```

Redis tests use `fakeredis`, so a running Redis server is not required.

## Current limitations

- Match result delivery is still stored in the API process.
- One matchmaking worker should run at a time.
- Metrics counters reset when the API restarts.
- Durable match history and acknowledgement-based delivery are not yet implemented.

## Next improvements

- Atomic Redis Lua script for safe multi-worker matching
- Durable match delivery and acknowledgement
- Prometheus metrics and Grafana dashboards
- Load testing and matchmaking benchmark reports
- Authentication and rate limiting
