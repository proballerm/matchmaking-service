# Matchmaking Service

A skill-based matchmaking backend built with FastAPI. The service balances match fairness and queue latency with an adaptive rating threshold while enforcing a hard maximum-wait SLA.

## Features

- Skill-based matching with adaptive rating thresholds
- SLA-forced matches for players waiting beyond the configured maximum
- Redis-backed queue persistence with automatic recovery after API restarts
- Atomic Redis match commits that prevent duplicate or lost matches across workers
- Durable per-player match inboxes with explicit acknowledgement
- Automatic match payload cleanup after all participants acknowledge delivery
- Shared Redis-backed adaptive threshold and system-wide metrics
- In-memory fallback for local development and deterministic tests
- Continuous background matchmaking loop
- Docker and Docker Compose support

## Architecture

```text
Clients
   |
FastAPI instances / matchmaking workers
   |
Shared Redis queue, match inboxes, threshold, and counters
   |
Atomic Lua state transitions
```

The engine is independent of FastAPI and accepts queue, match-store, and state-store backends through small interfaces.

- `src/core/engine.py` — orchestration, worker synchronization, match creation, delivery, and metrics
- `src/core/matcher.py` — threshold matching and SLA candidate selection
- `src/core/queue.py` — in-memory queue implementing the same claim contract
- `src/core/redis_queue.py` — Redis sorted-set and rating-hash queue
- `src/core/match_store.py` — atomic Redis publication, acknowledgement, and cleanup
- `src/core/state_store.py` — shared adaptive threshold and global counters
- `src/api/app.py` — HTTP API and background worker

Redis stores waiting players, durable match inboxes, the current adaptive threshold, and system-wide counters. Every worker refreshes the shared threshold before a matchmaking tick. Threshold adaptations use a Lua script, so concurrent workers update the same value atomically rather than overwriting one another.

The shared counters track successful enqueues, completed matches, and SLA-forced matches. Therefore every API instance returns the same totals from `/metrics`, and those values survive individual worker restarts.

Match creation and delivery remain atomic. A Lua script confirms both players are queued, removes them, stores the serialized match, initializes its acknowledgement count, and adds it to both inboxes as one operation. Final acknowledgement removes the retained payload automatically.

## Run with Redis

```bash
docker compose up --build
```

Then open:

- API documentation: `http://localhost:8000/docs`
- Health endpoint: `http://localhost:8000/health`
- Metrics: `http://localhost:8000/metrics`

Multiple processes can safely share the same state:

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

### Dequeue a player

```http
POST /dequeue
Content-Type: application/json

{
  "player_id": "p1"
}
```

### Poll a player's pending matches

```http
GET /players/p1/matches
```

### Acknowledge a delivered match

```http
POST /players/p1/matches/ack
Content-Type: application/json

{
  "match_id": "example-match-id"
}
```

Acknowledgement removes the match only from that player's pending inbox. After the final acknowledgement, the shared match payload is deleted automatically.

### Trigger one matchmaking tick

```http
POST /tick
Content-Type: application/json

{}
```

### Read system-wide metrics

```http
GET /metrics
```

Example fields:

```json
{
  "queue_depth": 12.0,
  "total_enqueues": 1000.0,
  "total_matches": 480.0,
  "sla_forced_matches": 12.0,
  "sla_forced_percentage": 2.5,
  "current_threshold": 135.0
}
```

## Tests

```bash
pytest -q
```

Redis tests use `fakeredis[lua]`, so a running Redis server is not required. The suite covers atomic multi-worker claims, all-or-nothing match commits, durable delivery and cleanup, shared counters, and atomic threshold adaptation across worker instances.

## Current limitations

- Match records are removed after delivery, so long-term match history requires a separate durable database.
- Metrics are available as JSON but are not yet exported in Prometheus format.
- The adaptive controller is intentionally simple and has not yet been tuned with production load data.

## Next improvements

- Add Prometheus metrics and Grafana dashboards
- Add load testing and benchmark reports
- Add PostgreSQL-backed long-term match history
- Add authentication and rate limiting
