MATCHMAKING SERVICE

A production-grade skill-based matchmaking backend built with FastAPI and a deterministic engine.
The service balances match fairness and latency using an adaptive rating threshold while enforcing
a hard maximum wait SLA. It runs continuously in the background and exposes a clean HTTP API for clients.


OVERVIEW

This service demonstrates real-world matchmaking system design. It continuously matches players
based on rating similarity, dynamically adjusts matching tolerance based on observed wait times,
and guarantees bounded latency through SLA enforcement.

Key capabilities:
- Skill-based matching using rating thresholds
- Adaptive threshold control to balance fairness versus wait time
- Hard SLA enforcement for maximum wait guarantees
- Continuous background matchmaking loop
- Pull-based match consumption model
- Live metrics for observability


ARCHITECTURE

The system is split into two layers.

ENGINE LAYER

The engine owns all matchmaking logic and state and is fully decoupled from the web framework.
It is deterministic and easily unit-testable.

Relevant files:
- src/core/engine.py  matchmaking engine, state management, metrics
- src/core/matcher.py  matching logic, adaptive threshold, SLA enforcement
- src/core/queue.py  in-memory queue with strict UTC time handling
- src/core/models.py  data models

API LAYER

The FastAPI layer handles HTTP requests, validation, serialization, concurrency control,
and lifecycle management of the background matchmaking loop.

Relevant file:
- src/api/app.py


MATCHING BEHAVIOR

NORMAL MATCHING

On each matchmaking tick, the engine scans the queue in join-time order and pairs players
whose rating difference is within the current threshold:

abs(rating_a - rating_b) <= current_threshold

Players matched in this phase are removed from the queue.

ADAPTIVE THRESHOLD CONTROL

After forming normal matches, the engine calculates the average wait time for players in
those matches and adjusts the threshold:

- Threshold increases when average wait exceeds the target
- Threshold decreases when average wait is below the target
- Threshold is clamped within configured minimum and maximum bounds

Only normal matches influence threshold adaptation. SLA-forced matches are excluded.

SLA ENFORCEMENT

If the oldest waiting player exceeds the configured maximum wait time, the engine force-matches
that player with the closest available partner regardless of rating difference. This guarantees
bounded latency even under unfavorable conditions.


TIME HANDLING

All timestamps are timezone-aware UTC.

- The engine is the single source of time
- The queue rejects naive datetimes
- The API normalizes all incoming timestamps to UTC


API REFERENCE

Health check
GET /health
Response: {"ok": true}

Enqueue player
POST /enqueue
Request body:
{
  "player_id": "p1",
  "rating": 1200,
  "timestamp_utc": "2026-01-01T00:00:00+00:00"
}

timestamp_utc is optional. If omitted, the server uses the current UTC time.
Duplicate enqueue requests return HTTP 409.

Dequeue player
POST /dequeue
Request body:
{"player_id": "p1"}

Poll matches
GET /matches
Returns matches created since the last poll and clears the internal match buffer.

Metrics
GET /metrics

Debug tick
POST /tick
Triggers exactly one matchmaking iteration and returns updated metrics.
This endpoint is intended for debugging and tests.


CONFIGURATION

Environment variables:
- ENABLE_BACKGROUND_TICK  enable or disable background matchmaking loop (default 1)
- TICK_INTERVAL_SECONDS  interval in seconds between matchmaking ticks (default 1.0)


RUNNING LOCALLY

Install dependencies:
pip install -e ".[dev]"

Start the server:
uvicorn api.app:app --reload

Open API docs:
http://localhost:8000/docs

Run tests:
pytest -q


RUNNING WITH DOCKER

Docker provides a simple way to build and run the service in a clean, isolated environment
without installing Python dependencies locally.

Prerequisites:
- Docker Desktop installed and running

Verify Docker:
docker --version

Build the image:
docker build -t matchmaking-service .

Run the container:
docker run --rm -p 8000:8000 matchmaking-service

Service endpoints:
http://localhost:8000/health
http://localhost:8000/docs

Custom configuration:

Disable background matchmaking:
docker run --rm -p 8000:8000 -e ENABLE_BACKGROUND_TICK=0 matchmaking-service

Change matchmaking tick interval:
docker run --rm -p 8000:8000 -e TICK_INTERVAL_SECONDS=0.5 matchmaking-service

Deterministic testing:
docker run --rm -p 8000:8000 -e ENABLE_BACKGROUND_TICK=0 matchmaking-service
curl -X POST http://localhost:8000/tick -H "Content-Type: application/json" -d "{}"
curl http://localhost:8000/matches


DESIGN CONSIDERATIONS

- In-memory state keeps the system simple, deterministic, and easy to test
- Engine logic is fully decoupled from FastAPI
- Adaptive control logic is isolated from SLA enforcement
- Pull-based match delivery avoids server push complexity
- Single-threaded engine with API-level locking ensures correctness


FUTURE ENHANCEMENTS

- Redis or database-backed persistence for horizontal scaling
- Prometheus-compatible metrics endpoint
- Structured JSON logging
- Authentication and rate limiting
- Durable match history and delivery guarantees