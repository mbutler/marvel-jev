from __future__ import annotations

from pathlib import Path

from marvel_bench.backends.openrouter import score_fights_openrouter
from marvel_bench.backends.semif import score_fights_semif
from marvel_bench.paths import DEFAULT_FIGHTS, DEFAULT_RESULTS


def run_score(
    *,
    backend: str,
    fights_path: Path = DEFAULT_FIGHTS,
    out_path: Path = DEFAULT_RESULTS,
    limit: int | None = None,
    concurrency: int = 4,
    model: str | None = None,
    semif_backend: str = "mlx",
    semif_mode: str = "direct",
    resume: bool = True,
) -> list[dict]:
    if backend == "openrouter":
        return score_fights_openrouter(
            fights_path,
            out_path=out_path,
            model=model,
            concurrency=concurrency,
            limit=limit,
            resume=resume,
        )
    if backend == "semif":
        kwargs = {
            "out_path": out_path,
            "backend": semif_backend,
            "mode": semif_mode,
            "limit": limit,
        }
        if model:
            kwargs["model"] = model
        return score_fights_semif(fights_path, **kwargs)
    raise SystemExit(f"Unknown backend: {backend} (expected openrouter|semif)")
