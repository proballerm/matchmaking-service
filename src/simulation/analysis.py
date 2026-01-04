from typing import List, Dict
import numpy as np


def _stats(data: List[float]) -> Dict[str, float]:
    if not data:
        return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0}

    arr = np.array(data)
    return {
        "avg": float(np.mean(arr)),
        "p50": float(np.percentile(arr, 50)),
        "p95": float(np.percentile(arr, 95)),
        "max": float(np.max(arr)),
    }


def summarize_simulation(simulation) -> Dict[str, float]:
    # Overall stats (what users feel)
    overall_wait = _stats(simulation.wait_times)
    rating_stats = _stats(simulation.rating_diffs)

    # Control-path stats (what controller learns from)
    normal_wait = _stats(simulation.normal_wait_times)

    # SLA-path stats (emergency behavior)
    sla_wait = _stats(simulation.sla_wait_times)

    matches_formed = len(simulation.wait_times) // 2
    sla_pct = (
        (simulation.sla_forced_matches / matches_formed) * 100
        if matches_formed > 0
        else 0.0
    )

    return {
        # Volume
        "players_created": len(simulation.players),
        "matches_formed": matches_formed,

        # User experience
        "avg_wait_time": overall_wait["avg"],
        "p95_wait_time": overall_wait["p95"],

        # Match quality
        "avg_rating_diff": rating_stats["avg"],
        "p95_rating_diff": rating_stats["p95"],

        # Controller health
        "avg_normal_wait": normal_wait["avg"],
        "p95_normal_wait": normal_wait["p95"],

        # SLA cost
        "avg_sla_wait": sla_wait["avg"],
        "p95_sla_wait": sla_wait["p95"],
        "sla_forced_matches": simulation.sla_forced_matches,
        "sla_forced_percentage": sla_pct,

        # Final state
        "final_threshold": simulation.matchmaker.current_threshold,
    }
