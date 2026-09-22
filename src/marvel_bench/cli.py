from __future__ import annotations

import argparse
from pathlib import Path

from marvel_bench.aggregate import aggregate_results
from marvel_bench.fetch_characters import fetch_marvel_characters
from marvel_bench.generate_fights import generate_fights
from marvel_bench.paths import (
    DEFAULT_CHARACTERS,
    DEFAULT_FIGHTS,
    DEFAULT_LEADERBOARD,
    DEFAULT_REPORT,
    DEFAULT_RESULTS,
    ROOT,
    load_env,
)
from marvel_bench.run_score import run_score
from marvel_bench.serve_results import serve_results
from marvel_bench.snapshot import build_snapshot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="marvel-bench",
        description="Marvel character matchup bench for OpenRouter Jev and SemIf",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="Fetch Marvel characters from Comic Vine")
    fetch.add_argument("--limit", type=int, default=None, help="Max characters to fetch")
    fetch.add_argument("--out", type=Path, default=DEFAULT_CHARACTERS)
    fetch.add_argument(
        "--min-interval",
        type=float,
        default=1.5,
        help="Seconds between Comic Vine requests (raise toward 18.5 if rate-limited)",
    )
    fetch.add_argument(
        "--max-scan",
        type=int,
        default=None,
        help="Max global character rows to scan while collecting Marvel",
    )

    gen = sub.add_parser("generate", help="Generate pairwise fight jobs")
    gen.add_argument("--characters", type=Path, default=None)
    gen.add_argument("--sample", action="store_true", help="Use bundled sample characters")
    gen.add_argument("--limit-chars", type=int, default=None)
    gen.add_argument("--max-pairs", type=int, default=None)
    gen.add_argument("--out", type=Path, default=DEFAULT_FIGHTS)

    score = sub.add_parser("score", help="Score fights with openrouter or semif")
    score.add_argument("--backend", choices=("openrouter", "semif"), required=True)
    score.add_argument("--fights", type=Path, default=DEFAULT_FIGHTS)
    score.add_argument("--out", type=Path, default=DEFAULT_RESULTS)
    score.add_argument("--limit", type=int, default=None, help="Score only first N fights")
    score.add_argument("--concurrency", type=int, default=4, help="OpenRouter workers")
    score.add_argument("--model", type=str, default=None)
    score.add_argument("--semif-backend", default="mlx", help="SemIf device backend")
    score.add_argument("--semif-mode", default="direct", help="SemIf mode")
    score.add_argument("--no-resume", action="store_true", help="Ignore existing results")

    report = sub.add_parser("report", help="Build throughput report and leaderboard")
    report.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    report.add_argument("--leaderboard", type=Path, default=DEFAULT_LEADERBOARD)
    report.add_argument("--out", type=Path, default=DEFAULT_REPORT)

    serve = sub.add_parser("serve", help="Local results UI")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)

    snap = sub.add_parser(
        "snapshot",
        help="Write a self-contained HTML snapshot (no server needed)",
    )
    snap.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    snap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    snap.add_argument("--leaderboard", type=Path, default=DEFAULT_LEADERBOARD)
    snap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "snapshot" / "index.html",
        help="Output HTML path",
    )
    snap.add_argument(
        "--max-fights",
        type=int,
        default=None,
        help="Optional cap on embedded fights (default: all)",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    load_env()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "fetch":
        fetch_marvel_characters(
            limit=args.limit,
            out_path=args.out,
            min_interval_s=args.min_interval,
            max_scan=args.max_scan,
        )
    elif args.command == "generate":
        generate_fights(
            characters_path=args.characters,
            limit_chars=args.limit_chars,
            max_pairs=args.max_pairs,
            out_path=args.out,
            use_sample=args.sample,
        )
    elif args.command == "score":
        run_score(
            backend=args.backend,
            fights_path=args.fights,
            out_path=args.out,
            limit=args.limit,
            concurrency=args.concurrency,
            model=args.model,
            semif_backend=args.semif_backend,
            semif_mode=args.semif_mode,
            resume=not args.no_resume,
        )
    elif args.command == "report":
        aggregate_results(
            results_path=args.results,
            leaderboard_path=args.leaderboard,
            report_path=args.out,
        )
    elif args.command == "serve":
        serve_results(host=args.host, port=args.port)
    elif args.command == "snapshot":
        build_snapshot(
            results_path=args.results,
            report_path=args.report,
            leaderboard_path=args.leaderboard,
            out_path=args.out,
            max_fights=args.max_fights,
        )
    else:
        parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
