from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any

from marvel_bench.cards import fighter_card
from marvel_bench.paths import (
    DEFAULT_FIGHTS,
    load_characters,
    resolve_characters_path,
    write_jsonl,
)


def make_fight(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    card_a = fighter_card(a)
    card_b = fighter_card(b)
    id_a, id_b = int(a["id"]), int(b["id"])
    lo, hi = sorted((id_a, id_b))
    return {
        "id": f"fight-{lo}-{hi}",
        "a_id": id_a,
        "b_id": id_b,
        "a_name": a["name"],
        "b_name": b["name"],
        "state": {
            "fighter_a": card_a,
            "fighter_b": card_b,
        },
        "question": {
            "id": "winner",
            "type": "choice",
            "instructions": (
                "Who wins a fair fight between fighter_a and fighter_b? "
                "Assume a neutral arena, no outside help, standard gear, and comic-book continuity."
            ),
            "criteria": {
                "a": f"{a['name']} wins.",
                "b": f"{b['name']} wins.",
            },
        },
    }


def generate_fights(
    *,
    characters_path: Path | None = None,
    limit_chars: int | None = None,
    max_pairs: int | None = None,
    out_path: Path = DEFAULT_FIGHTS,
    use_sample: bool = False,
) -> list[dict[str, Any]]:
    path = resolve_characters_path(characters_path, prefer_sample=use_sample)
    characters = load_characters(path)
    characters = sorted(characters, key=lambda c: (-(c.get("count_of_issue_appearances") or 0), c["name"]))
    if limit_chars is not None:
        characters = characters[:limit_chars]

    fights: list[dict[str, Any]] = []
    for a, b in itertools.combinations(characters, 2):
        fights.append(make_fight(a, b))
        if max_pairs is not None and len(fights) >= max_pairs:
            break

    write_jsonl(out_path, fights)
    print(
        f"Wrote {len(fights)} fights from {len(characters)} characters "
        f"({path.name}) -> {out_path}"
    )
    return fights
