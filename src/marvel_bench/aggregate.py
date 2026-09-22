from __future__ import annotations

import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from marvel_bench.paths import (
    DEFAULT_LEADERBOARD,
    DEFAULT_REPORT,
    DEFAULT_RESULTS,
    read_jsonl,
    write_json,
)


def aggregate_results(
    results_path: Path = DEFAULT_RESULTS,
    *,
    leaderboard_path: Path = DEFAULT_LEADERBOARD,
    report_path: Path = DEFAULT_REPORT,
) -> dict[str, Any]:
    if not results_path.exists():
        raise SystemExit(
            f"No results at {results_path}. Run `marvel-bench score` first."
        )
    rows = read_jsonl(results_path)
    by_backend: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_backend[row.get("backend") or "unknown"].append(row)

    backends: dict[str, Any] = {}
    overall_leaderboard: dict[str, dict[str, Any]] = {}

    for backend, items in by_backend.items():
        ok = [r for r in items if "error" not in r and r.get("choice") in ("a", "b")]
        errs = [r for r in items if "error" in r]
        latencies = [float(r["latency_ms"]) for r in ok if r.get("latency_ms") is not None]
        costs = [float(r["cost"]) for r in ok if isinstance(r.get("cost"), (int, float))]

        wins: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"wins": 0, "losses": 0, "name": "", "id": None}
        )
        for r in ok:
            a_key = str(r["a_id"])
            b_key = str(r["b_id"])
            wins[a_key]["id"] = r["a_id"]
            wins[a_key]["name"] = r["a_name"]
            wins[b_key]["id"] = r["b_id"]
            wins[b_key]["name"] = r["b_name"]
            if r.get("choice") == "a":
                wins[a_key]["wins"] += 1
                wins[b_key]["losses"] += 1
            elif r.get("choice") == "b":
                wins[b_key]["wins"] += 1
                wins[a_key]["losses"] += 1

        standings = []
        for entry in wins.values():
            games = entry["wins"] + entry["losses"]
            standings.append(
                {
                    **entry,
                    "games": games,
                    "win_rate": (entry["wins"] / games) if games else 0.0,
                    "backend": backend,
                }
            )
        standings.sort(key=lambda e: (-e["win_rate"], -e["wins"], e["name"]))

        mean_latency = statistics.mean(latencies) if latencies else None
        rate = (1000.0 / mean_latency) if mean_latency else None

        backends[backend] = {
            "total_rows": len(items),
            "ok": len(ok),
            "errors": len(errs),
            "mean_latency_ms": round(mean_latency, 2) if mean_latency is not None else None,
            "fights_per_sec_est": round(rate, 3) if rate is not None else None,
            "total_cost": round(sum(costs), 6) if costs else 0.0,
            "model": next((r.get("model") for r in ok if r.get("model")), None),
            "leaderboard": standings,
        }

        for entry in standings:
            key = f"{backend}:{entry['id']}"
            overall_leaderboard[key] = entry

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results_path": str(results_path),
        "backends": backends,
    }
    write_json(report_path, report)
    write_json(
        leaderboard_path,
        {
            "generated_at": report["generated_at"],
            "by_backend": {b: backends[b]["leaderboard"] for b in backends},
        },
    )

    print(f"Report -> {report_path}")
    for backend, stats in backends.items():
        print(
            f"[{backend}] ok={stats['ok']} err={stats['errors']} "
            f"mean_latency_ms={stats['mean_latency_ms']} "
            f"~{stats['fights_per_sec_est']} fights/s "
            f"cost=${stats['total_cost']}"
        )
        top = stats["leaderboard"][:5]
        if top:
            print("  Top:")
            for i, e in enumerate(top, 1):
                print(
                    f"    {i}. {e['name']} "
                    f"{e['wins']}-{e['losses']} ({e['win_rate']:.0%})"
                )
    return report
