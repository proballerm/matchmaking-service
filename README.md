# Matchmaking Service

A skill-based matchmaking backend built with FastAPI. The service balances match fairness and queue latency with an adaptive rating threshold while enforcing a hard maximum-wait SLA.

## Features

- Skill-based matching with adaptive rating thresholds
- SLA-forced matches for players waiting beyond the configured maximum
- Redis-backed queue persistence with automatic recovery after API restarts
- Atomic Redis match commits that prevent duplicate or lost matches across workers
- Durable per-player match inboxes with explicit acknowledgement
- Automatic match payload cleanup after all participants acknowledge delivery
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
Shared Redis queue + durable player inboxes
   |
Atomic Lua claim, publish, acknowledge, and cleanup operations
```

The engine is independent of FastAPI and accepts queue and match-store backends through small interfaces.

- `src/core/engine.py` — orchestration, worker synchronization, match creation, and delivery
- `src/core/matcher.py` — threshold matching and SLA candidate selection
- `src/core/queue.py` — in-memory queue implementing the same claim contract
- `src/core/redis_queue.py` — Redis sorted-set and rating-hash queue
- `src/core/match_store.py` — in-memory delivery plus atomic Redis publication and cleanup
- `src/api/app.py` — HTTP API and background worker

Redis stores waiting players in a sorted set scored by UTC join timestamp and stores ratings in a hash. Workers identify candidate pairs independently. For each candidate, the engine builds the complete match record before attempting the commit.

A Redis Lua script then performs all of the following as one indivisible operation:

1. Confirms both players are still queued.
2. Removes both players and their rating metadata.
3. Stores the serialized match record.
4. Stores the number of required acknowledgements.
5. Adds the match ID to each player's inbox.

If either player was already claimed, the script returns failure and writes nothing. This removes the crash window where a worker could remove players and fail before publishing their match.

Acknowledgements are also processed atomically. Redis removes the match only from the acknowledging player's inbox and decrements the remaining acknowledgement count. When the final participant acknowledges, Redis deletes both the stored match payload and its acknowledgement counter. Duplicate or invalid acknowledgements do not decrement the count.

## Run with Redis

```bash
docker compose up --build
```

Then open:

- API documentation: `http://localhost:8000/docs`
- Health endpoint: `http://localhost:8000/health`
- Metrics: `http://localhost:8000/metrics`

Multiple processes can share the same Redis state:

```bash
REDIS_URL=redis://localhost:6379/0 uvicorn api.app:app --workers 4
```

## Run without Redis

```bash
pip install -e ".[dev]"
uvicorn api.app:app --reload
```

Without `REDIS_URL`, the service uses in-memory queue and match-store implementations.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | unset | Redis connection URL. When unset, the service uses memory. |
| `REDIS_NAMESPACE` | `matchmaking` | Prefix for Redis queue and match-delivery keys. |
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

Acknowledgement removes the match only from that player's pending inbox. The other participant acknowledges independently. After the final acknowledgement, the shared match payload is deleted automatically.

### Legacy global match feed

```http
GET /matches
```

This endpoint is process-local and retained only for backward compatibility. New clients should use the player-specific endpoints.

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

Redis tests use `fakeredis[lua]`, so a running Redis server is not required. The suite covers atomic multi-worker claims, all-or-nothing match commits, failed-claim rollback behavior, persistence, player-scoped acknowledgements, duplicate acknowledgements, and automatic cleanup after final delivery.

## Current limitations

- Metrics counters are process-local and reset when an API instance restarts.
- Adaptive threshold state is not yet shared across workers.
- Match records are removed after delivery, so long-term match history requires a separate durable database.

## Next improvements

- Share threshold and metrics state across workers
- Add Prometheus metrics and Grafana dashboards
- Add load testing and benchmark reports
- Add authentication and rate limiting
- Add PostgreSQL-backed long-term match history
