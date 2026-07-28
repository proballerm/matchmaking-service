import csv
import json
import subprocess
import sys
from pathlib import Path


def test_benchmark_summary_extracts_aggregate_metrics(tmp_path: Path):
    stats = tmp_path / "run_stats.csv"
    output = tmp_path / "summary.json"

    fieldnames = [
        "Type",
        "Name",
        "Request Count",
        "Failure Count",
        "Median Response Time",
        "Average Response Time",
        "Min Response Time",
        "Max Response Time",
        "Requests/s",
        "95%",
        "99%",
    ]
    with stats.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "Type": "",
                "Name": "Aggregated",
                "Request Count": "1000",
                "Failure Count": "5",
                "Median Response Time": "12",
                "Average Response Time": "18.5",
                "Min Response Time": "2",
                "Max Response Time": "240",
                "Requests/s": "155.25",
                "95%": "45",
                "99%": "90",
            }
        )

    subprocess.run(
        [
            sys.executable,
            "loadtest/summarize_results.py",
            "--stats",
            str(stats),
            "--output",
            str(output),
            "--users",
            "200",
            "--spawn-rate",
            "20",
            "--run-time",
            "2m",
        ],
        check=True,
    )

    summary = json.loads(output.read_text(encoding="utf-8"))
    assert summary["scenario"]["users"] == 200
    assert summary["results"]["requests_per_second"] == 155.25
    assert summary["results"]["p95_response_ms"] == 45.0
    assert summary["results"]["failure_rate"] == 0.005
