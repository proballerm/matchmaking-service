#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-http://localhost:8000}"
USERS="${USERS:-200}"
SPAWN_RATE="${SPAWN_RATE:-20}"
RUN_TIME="${RUN_TIME:-2m}"
RESULT_DIR="${RESULT_DIR:-benchmark/results}"
RUN_NAME="${RUN_NAME:-matchmaking-$(date -u +%Y%m%dT%H%M%SZ)}"

mkdir -p "$RESULT_DIR"
PREFIX="$RESULT_DIR/$RUN_NAME"

echo "Running matchmaking benchmark"
echo "  host:       $HOST"
echo "  users:      $USERS"
echo "  spawn rate: $SPAWN_RATE users/s"
echo "  duration:   $RUN_TIME"
echo "  output:     $PREFIX"

locust \
  -f loadtest/locustfile.py \
  --headless \
  --host "$HOST" \
  --users "$USERS" \
  --spawn-rate "$SPAWN_RATE" \
  --run-time "$RUN_TIME" \
  --csv "$PREFIX" \
  --html "$PREFIX.html" \
  --only-summary

python loadtest/summarize_results.py \
  --stats "${PREFIX}_stats.csv" \
  --output "${PREFIX}_summary.json" \
  --users "$USERS" \
  --spawn-rate "$SPAWN_RATE" \
  --run-time "$RUN_TIME"

echo "Benchmark complete: ${PREFIX}_summary.json"
