from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import httpx

from marvel_bench.paths import (
    DEFAULT_OPENROUTER_MODEL,
    DEFAULT_RESULTS,
    OPENROUTER_SYSTEMONE_URL,
    append_jsonl,
    read_jsonl,
    require_env,
)


def fight_to_openrouter_body(fight: dict[str, Any], model: str) -> dict[str, Any]:
    q = fight["question"]
    return {
        "model": model,
        "state": fight["state"],
        "questions": {
            q["id"]: {
                "type": q["type"],
                "instructions": q["instructions"],
                "criteria": q["criteria"],
            }
        },
    }


def _pick_winner(answer: dict[str, Any], fight: dict[str, Any]) -> dict[str, Any]:
    """Normalize a System One choice answer into a common result shape."""
    choice = answer.get("choice")
    probs = answer.get("probabilities") or {}
    if not isinstance(probs, dict):
        probs = {}

    if choice is None and probs:
        choice = max(probs.items(), key=lambda kv: float(kv[1]))[0]

    winner_id = None
    winner_name = None
    if choice == "a":
        winner_id = fight["a_id"]
        winner_name = fight["a_name"]
    elif choice == "b":
        winner_id = fight["b_id"]
        winner_name = fight["b_name"]

    return {
        "choice": choice,
        "probabilities": {str(k): float(v) for k, v in probs.items()},
        "winner_id": winner_id,
        "winner_name": winner_name,
        "confidence": answer.get("confidence"),
    }


def score_one(
    client: httpx.Client,
    fight: dict[str, Any],
    *,
    model: str,
    url: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    body = fight_to_openrouter_body(fight, model)
    resp = client.post(url, json=body)
    latency_ms = (time.perf_counter() - started) * 1000
    resp.raise_for_status()
    payload = resp.json()

    answers = payload.get("answers") or {}
    winner_answer = answers.get(fight["question"]["id"]) or next(iter(answers.values()), {})
    picked = _pick_winner(winner_answer if isinstance(winner_answer, dict) else {}, fight)
    usage = payload.get("usage") or {}

    return {
        "id": fight["id"],
        "backend": "openrouter",
        "model": payload.get("model") or model,
        "a_id": fight["a_id"],
        "b_id": fight["b_id"],
        "a_name": fight["a_name"],
        "b_name": fight["b_name"],
        "choice": picked["choice"],
        "probabilities": picked["probabilities"],
        "confidence": picked.get("confidence"),
        "winner_id": picked["winner_id"],
        "winner_name": picked["winner_name"],
        "latency_ms": round(latency_ms, 2),
        "usage": usage,
        "cost": usage.get("cost"),
        "raw_answer": winner_answer,
        "provider": payload.get("provider"),
        "request_id": payload.get("id"),
    }


def score_fights_openrouter(
    fights_path: Path,
    *,
    out_path: Path = DEFAULT_RESULTS,
    model: str | None = None,
    concurrency: int = 4,
    limit: int | None = None,
    resume: bool = True,
) -> list[dict[str, Any]]:
    api_key = require_env("OPENROUTER_API_KEY")
    model = model or os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)
    fights = read_jsonl(fights_path)
    if limit is not None:
        fights = fights[:limit]

    done_ids: set[str] = set()
    if resume and out_path.exists():
        for row in read_jsonl(out_path):
            if row.get("backend") == "openrouter" and row.get("id"):
                done_ids.add(row["id"])

    pending = [f for f in fights if f["id"] not in done_ids]
    print(f"OpenRouter: {len(pending)} pending / {len(fights)} total (model={model})")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/local/marvel-bench",
        "X-OpenRouter-Title": "Marvel Matchup Bench",
    }

    results: list[dict[str, Any]] = []
    errors = 0
    t0 = time.perf_counter()

    with httpx.Client(timeout=120.0, headers=headers) as client:

        def _run(fight: dict[str, Any]) -> dict[str, Any]:
            return score_one(client, fight, model=model, url=OPENROUTER_SYSTEMONE_URL)

        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
            futures = {pool.submit(_run, fight): fight for fight in pending}
            for i, fut in enumerate(as_completed(futures), start=1):
                fight = futures[fut]
                try:
                    row = fut.result()
                    append_jsonl(out_path, row)
                    results.append(row)
                except Exception as exc:  # noqa: BLE001 — surface per-fight failures
                    errors += 1
                    err_row = {
                        "id": fight["id"],
                        "backend": "openrouter",
                        "model": model,
                        "a_id": fight["a_id"],
                        "b_id": fight["b_id"],
                        "a_name": fight["a_name"],
                        "b_name": fight["b_name"],
                        "error": str(exc),
                    }
                    append_jsonl(out_path, err_row)
                    print(f"FAIL {fight['id']}: {exc}")
                if i % 10 == 0 or i == len(pending):
                    elapsed = time.perf_counter() - t0
                    rate = i / elapsed if elapsed else 0
                    print(f"Scored {i}/{len(pending)} ({rate:.2f} fights/s, errors={errors})")

    elapsed = time.perf_counter() - t0
    print(
        f"OpenRouter done: {len(results)} ok, {errors} errors in {elapsed:.1f}s "
        f"-> {out_path}"
    )
    return results
