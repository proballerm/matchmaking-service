# Matchmaking Service

A skill-based matchmaking backend built with FastAPI. The service balances match fairness and queue latency with an adaptive rating threshold while enforcing a hard maximum-wait SLA.

## Features

- Skill-based matching with adaptive rating thresholds
- SLA-forced matches for players waiting beyond the configured maximum
- Redis-backed queue persistence with automatic recovery after API restarts
- Atomic Redis player claims that prevent duplicate matches across workers
- Durable per-player match inboxes with explicit acknowledgement
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
Atomic Lua player claims
```

The engine is independent of FastAPI and accepts queue and match-store backends through small interfaces.

- `src/core/engine.py` — orchestration, worker synchronization, match creation, and delivery
- `src/core/matcher.py` — threshold matching, SLA enforcement, and atomic claim usage
- `src/core/queue.py` — in-memory queue implementing the same claim contract
- `src/core/redis_queue.py` — Redis sorted-set, rating hash, and Lua claim script
- `src/core/match_store.py` — in-memory and Redis per-player match inboxes
- `src/api/app.py` — HTTP API and background worker

Redis stores waiting players in a sorted set scored by UTC join timestamp. Ratings are stored in a hash. Workers identify candidate pairs independently, but a Lua script verifies and removes both players atomically so only one worker can successfully claim them.

After a match is created, Redis stores the serialized result and appends its ID to a separate inbox for each participating player. A player keeps receiving the result until that player explicitly acknowledges it. One player's acknowledgement does not remove the result from the other player's inbox.

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

Example response:

```json
{
  "player_id": "p1",
  "matches": [
    {
      "match_id": "example-match-id",
      "player_ids": ["p1", "p2"],
      "created_at": "2026-01-01T00:00:00+00:00",
      "rating_diff": 25.0,
      "sla_forced": false,
      "threshold_at_match": 100.0
    }
  ]
}
```

### Acknowledge a delivered match

```http
POST /players/p1/matches/ack
Content-Type: application/json

{
  "match_id": "example-match-id"
}
```

Acknowledgement removes the match only from `p1`'s pending inbox. The other participant must acknowledge independently.

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

Redis tests use `fakeredis[lua]`, so a running Redis server is not required. The suite covers atomic multi-worker claims, persistence across match-store recreation, player-scoped acknowledgements, and independent delivery to both participants.

## Current limitations

- Queue claiming and match publication are separate Redis operations; a worker crash between them could claim players before publishing their result.
- Match payloads are retained after both players acknowledge them; retention cleanup is not implemented yet.
- Metrics counters are process-local and reset when an API instance restarts.
- Adaptive threshold state is not yet shared across workers.

## Next improvements

- Combine player claim and match publication into one atomic Redis operation
- Add match retention and cleanup after both acknowledgements
- Share threshold and metrics state across workers
- Add Prometheus metrics and Grafana dashboards
- Add load testing and benchmark reports
