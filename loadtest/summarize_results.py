from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def as_float(row: Dict[str, str], key: str) -> float:
    value = row.get(key, "")
    return float(value) if value not in (None, "") else 0.0


def load_aggregate(stats_path: Path) -> Dict[str, str]:
    with stats_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        if row.get("Name") == "Aggregated":
            return row

    raise ValueError(f"Aggregated row not found in {stats_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize Locust CSV output")
    parser.add_argument("--stats", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--users", required=True, type=int)
    parser.add_argument("--spawn-rate", required=True, type=float)
    parser.add_argument("--run-time", required=True)
    args = parser.parse_args()

    row = load_aggregate(args.stats)
    requests = int(as_float(row, "Request Count"))
    failures = int(as_float(row, "Failure Count"))
    failure_rate = failures / requests if requests else 0.0

    summary: Dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scenario": {
            "users": args.users,
            "spawn_rate_users_per_second": args.spawn_rate,
            "run_time": args.run_time,
        },
        "results": {
            "requests": requests,
            "failures": failures,
            "failure_rate": failure_rate,
            "requests_per_second": as_float(row, "Requests/s"),
            "median_response_ms": as_float(row, "Median Response Time"),
            "average_response_ms": as_float(row, "Average Response Time"),
            "min_response_ms": as_float(row, "Min Response Time"),
            "max_response_ms": as_float(row, "Max Response Time"),
            "p95_response_ms": as_float(row, "95%"),
            "p99_response_ms": as_float(row, "99%"),
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
