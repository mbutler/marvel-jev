from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from marvel_bench.cards import card_text
from marvel_bench.paths import (
    DATA_DIR,
    DEFAULT_RESULTS,
    DEFAULT_SEMIF_MODEL,
    DEFAULT_SEMIF_REVISION,
    append_jsonl,
    read_jsonl,
    write_jsonl,
)


def fight_to_semif_row(fight: dict[str, Any]) -> dict[str, Any]:
    state_a = card_text(fight["state"]["fighter_a"])
    state_b = card_text(fight["state"]["fighter_b"])
    q = fight["question"]
    return {
        "id": fight["id"],
        "state": f"Fighter A\n{state_a}\n\nFighter B\n{state_b}",
        "question": q["instructions"],
        "options": [
            {"id": "a", "description": q["criteria"]["a"]},
            {"id": "b", "description": q["criteria"]["b"]},
        ],
        # Carry ids for result mapping after semif-score
        "_meta": {
            "a_id": fight["a_id"],
            "b_id": fight["b_id"],
            "a_name": fight["a_name"],
            "b_name": fight["b_name"],
        },
    }


def _strip_meta_for_semif(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k != "_meta"}


def _normalize_semif_result(
    fight_meta: dict[str, Any],
    semif_row: dict[str, Any],
    *,
    model: str,
) -> dict[str, Any]:
    scores = (
        semif_row.get("scores")
        or semif_row.get("probabilities")
        or semif_row.get("option_scores")
        or {}
    )
    # SemIf may return list of {id, score} or dict
    probs: dict[str, float] = {}
    if isinstance(scores, dict):
        probs = {str(k): float(v) for k, v in scores.items()}
    elif isinstance(scores, list):
        for item in scores:
            if isinstance(item, dict) and "id" in item:
                val = item.get("score", item.get("probability", item.get("prob")))
                if val is not None:
                    probs[str(item["id"])] = float(val)

    choice = semif_row.get("choice") or semif_row.get("argmax") or semif_row.get("prediction")
    if choice is None and probs:
        choice = max(probs.items(), key=lambda kv: kv[1])[0]

    winner_id = None
    winner_name = None
    if choice == "a":
        winner_id = fight_meta["a_id"]
        winner_name = fight_meta["a_name"]
    elif choice == "b":
        winner_id = fight_meta["b_id"]
        winner_name = fight_meta["b_name"]

    latency_ms = semif_row.get("latency_ms")
    if latency_ms is None and semif_row.get("timing"):
        timing = semif_row["timing"]
        if isinstance(timing, dict):
            latency_ms = timing.get("total_ms") or timing.get("latency_ms")

    return {
        "id": fight_meta["id"],
        "backend": "semif",
        "model": semif_row.get("model") or model,
        "a_id": fight_meta["a_id"],
        "b_id": fight_meta["b_id"],
        "a_name": fight_meta["a_name"],
        "b_name": fight_meta["b_name"],
        "choice": choice,
        "probabilities": probs,
        "winner_id": winner_id,
        "winner_name": winner_name,
        "latency_ms": latency_ms,
        "semif": {
            "prompt_sha256": semif_row.get("prompt_sha256"),
            "revision": semif_row.get("revision"),
            "raw_keys": sorted(semif_row.keys()),
        },
    }


def score_fights_semif(
    fights_path: Path,
    *,
    out_path: Path = DEFAULT_RESULTS,
    model: str = DEFAULT_SEMIF_MODEL,
    revision: str = DEFAULT_SEMIF_REVISION,
    backend: str = "mlx",
    mode: str = "direct",
    limit: int | None = None,
    semif_bin: str | None = None,
) -> list[dict[str, Any]]:
    """Convert fights to SemIf JSONL and invoke `semif-score`."""
    exe = semif_bin or shutil.which("semif-score")
    if not exe:
        raise SystemExit(
            "semif-score not found on PATH. Install SemIf with MLX support:\n"
            "  git clone https://github.com/TheoLeeCJ/SemIf.git\n"
            "  cd SemIf && pip install -e '.[test,mlx]'\n"
            "Then re-run with --backend semif"
        )

    fights = read_jsonl(fights_path)
    if limit is not None:
        fights = fights[:limit]

    semif_rows = [fight_to_semif_row(f) for f in fights]
    meta_by_id = {r["id"]: {**r["_meta"], "id": r["id"]} for r in semif_rows}
    input_path = DATA_DIR / "fights.semif.jsonl"
    raw_out = DATA_DIR / "results.semif.raw.jsonl"
    write_jsonl(input_path, [_strip_meta_for_semif(r) for r in semif_rows])

    cmd = [
        exe,
        "--mode",
        mode,
        "--backend",
        backend,
        "--model",
        model,
        "--revision",
        revision,
        "--input",
        str(input_path),
        "--output",
        str(raw_out),
    ]
    print("Running:", " ".join(cmd))
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    elapsed = time.perf_counter() - t0
    if proc.returncode != 0:
        raise SystemExit(
            f"semif-score failed ({proc.returncode})\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    print(proc.stdout)
    if proc.stderr:
        print(proc.stderr)

    raw_results = read_jsonl(raw_out) if raw_out.exists() else []
    normalized: list[dict[str, Any]] = []
    for row in raw_results:
        rid = row.get("id")
        if rid not in meta_by_id:
            continue
        norm = _normalize_semif_result(meta_by_id[rid], row, model=model)
        if norm.get("latency_ms") is None and raw_results:
            # Approximate per-row latency from wall clock if SemIf omitted timing
            norm["latency_ms"] = round((elapsed / len(raw_results)) * 1000, 2)
        append_jsonl(out_path, norm)
        normalized.append(norm)

    rate = len(normalized) / elapsed if elapsed else 0
    print(
        f"SemIf done: {len(normalized)} results in {elapsed:.1f}s "
        f"({rate:.2f} fights/s) -> {out_path}"
    )
    return normalized
