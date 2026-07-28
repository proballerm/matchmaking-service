# Matchmaking Service

A skill-based matchmaking backend built with FastAPI. The service balances match fairness and queue latency with an adaptive rating threshold while enforcing a hard maximum-wait SLA.

## Features

- Skill-based matching with adaptive rating thresholds
- SLA-forced matches for players waiting beyond the configured maximum
- Redis-backed queue persistence with automatic recovery after API restarts
- Atomic Redis player claims that prevent duplicate matches across workers
- In-memory fallback for local development and deterministic tests
- Continuous background matchmaking loop
- Docker and Docker Compose support
- Metrics for queue depth, match count, threshold state, and SLA-forced matches

## Architecture

```text
Clients
   |
FastAPI instances / matchmaking workers
   |
Shared Redis queue
   |
Atomic Lua claim operation
```

The engine is independent of FastAPI and accepts any queue backend matching the queue interface.

- `src/core/engine.py` — orchestration, worker-state synchronization, metrics, and match records
- `src/core/matcher.py` — threshold matching, SLA enforcement, and atomic claim usage
- `src/core/queue.py` — in-memory queue implementing the same claim contract
- `src/core/redis_queue.py` — Redis sorted-set, rating hash, and Lua claim script
- `src/api/app.py` — HTTP API and background worker

Redis stores player IDs in a sorted set scored by UTC join timestamp. Ratings are stored in a Redis hash. Each worker reads candidates independently, but a Redis Lua script verifies and removes both players as one indivisible operation. Only one worker can successfully claim a pair.

This supports multiple active matchmaking workers without assigning the same player to two matches.

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

Multiple processes can share the same queue:

```bash
REDIS_URL=redis://localhost:6379/0 uvicorn api.app:app --workers 4
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

## Atomic claim behavior

Workers first identify a candidate pair from the shared queue. They then call `claim_players`.

The Redis implementation executes a Lua script that:

1. Confirms every requested player is still queued.
2. Removes all players from the sorted set.
3. Removes their rating metadata.
4. Returns success to exactly one worker.

When another worker already claimed either player, the script returns failure without removing anyone else. The losing worker refreshes the queue and continues.

## Tests

```bash
pytest -q
```

Redis tests use `fakeredis[lua]`, so a running Redis server is not required. The test suite includes a two-worker race that verifies each player can appear in at most one match.

## Current limitations

- Match result delivery is still stored in the API process that created the match.
- Metrics counters are process-local and reset when an API instance restarts.
- Durable match history and acknowledgement-based delivery are not yet implemented.
- Adaptive threshold state is not yet shared across workers.

## Next improvements

- Durable per-player match delivery and acknowledgement in Redis
- Shared threshold and metrics state across workers
- Prometheus metrics and Grafana dashboards
- Load testing and matchmaking benchmark reports
- Authentication and rate limiting
