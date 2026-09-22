from __future__ import annotations

from pathlib import Path

from marvel_bench.aggregate import aggregate_results
from marvel_bench.backends.semif import fight_to_semif_row
from marvel_bench.generate_fights import generate_fights
from marvel_bench.paths import SAMPLE_CHARACTERS, write_jsonl


def test_generate_sample_pairs(tmp_path: Path) -> None:
    out = tmp_path / "fights.jsonl"
    fights = generate_fights(
        characters_path=SAMPLE_CHARACTERS,
        max_pairs=5,
        out_path=out,
        use_sample=True,
    )
    assert len(fights) == 5
    assert out.exists()
    row = fights[0]
    assert row["question"]["type"] == "choice"
    assert set(row["question"]["criteria"]) == {"a", "b"}
    assert "fighter_a" in row["state"]


def test_semif_row_shape() -> None:
    fights = generate_fights(
        characters_path=SAMPLE_CHARACTERS,
        max_pairs=1,
        out_path=Path("/tmp/marvel-bench-test-fights.jsonl"),
        use_sample=True,
    )
    row = fight_to_semif_row(fights[0])
    assert row["id"].startswith("fight-")
    assert len(row["options"]) == 2
    assert "Fighter A" in row["state"]


def test_aggregate(tmp_path: Path) -> None:
    results = tmp_path / "results.jsonl"
    write_jsonl(
        results,
        [
            {
                "id": "fight-1-2",
                "backend": "openrouter",
                "a_id": 1,
                "b_id": 2,
                "a_name": "A",
                "b_name": "B",
                "choice": "a",
                "winner_id": 1,
                "winner_name": "A",
                "latency_ms": 100,
                "cost": 0.0001,
                "probabilities": {"a": 0.8, "b": 0.2},
            },
            {
                "id": "fight-1-3",
                "backend": "openrouter",
                "a_id": 1,
                "b_id": 3,
                "a_name": "A",
                "b_name": "C",
                "choice": "b",
                "winner_id": 3,
                "winner_name": "C",
                "latency_ms": 120,
                "cost": 0.0002,
                "probabilities": {"a": 0.4, "b": 0.6},
            },
        ],
    )
    report = aggregate_results(
        results_path=results,
        leaderboard_path=tmp_path / "leaderboard.json",
        report_path=tmp_path / "report.json",
    )
    assert report["backends"]["openrouter"]["ok"] == 2
    assert report["backends"]["openrouter"]["total_cost"] == 0.0003
    board = report["backends"]["openrouter"]["leaderboard"]
    assert board[0]["name"] in {"A", "C"}
