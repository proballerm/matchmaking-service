# Matchmaking Service Benchmark Report

This report is intentionally a template until a benchmark is executed on documented hardware. Do not replace placeholders with estimates.

## Environment

- Date (UTC): `<YYYY-MM-DD>`
- Commit: `<git SHA>`
- Host OS: `<OS and version>`
- CPU: `<model and core count>`
- Memory: `<RAM>`
- Docker version: `<version>`
- API workers: `<count>`
- Redis deployment: `<local/container/managed>`

## Scenario

Command:

```bash
USERS=200 SPAWN_RATE=20 RUN_TIME=2m bash loadtest/run_benchmark.sh
```

Workload behavior:

1. Each simulated player joins with a randomized rating.
2. Players poll their durable match inbox.
3. Matched players acknowledge delivery.
4. Players rejoin under a new ID and repeat.
5. A smaller percentage of traffic reads system metrics.

## Results

Copy values from the generated `*_summary.json` file.

| Metric | Result |
|---|---:|
| Concurrent users | `<value>` |
| Total requests | `<value>` |
| Requests/second | `<value>` |
| Median response time | `<value> ms` |
| p95 response time | `<value> ms` |
| p99 response time | `<value> ms` |
| Failure rate | `<value>%` |
| Matches created | `<value>` |
| SLA-forced percentage | `<value>%` |

## Interpretation

Document what constrained the run. Examples include CPU saturation, Redis latency, API worker count, queue growth, or polling traffic. Separate observations from hypotheses.

## Resume bullet after verification

Use only numbers produced by a repeatable run:

> Built a horizontally scalable FastAPI and Redis matchmaking service with atomic Lua state transitions; sustained `<verified RPS>` requests/second at `<verified p95>` ms p95 latency across `<verified users>` concurrent simulated players with `<verified failure rate>%` failures.

## Reproduction artifacts

Commit these or attach them to a release when publishing results:

- `*_stats.csv`
- `*_failures.csv`
- `*_exceptions.csv`
- `*.html`
- `*_summary.json`
- Host and container configuration
