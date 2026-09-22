from __future__ import annotations

from typing import Any


def _names(items: Any, *, limit: int = 8) -> list[str]:
    if not items:
        return []
    names: list[str] = []
    for item in items:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            name = item.get("name")
            if name:
                names.append(str(name))
        if len(names) >= limit:
            break
    return names


def fighter_card(character: dict, *, max_summary: int = 400) -> dict:
    """Compact structured card used as OpenRouter/SemIf state."""
    deck = (character.get("deck") or "").strip().replace("\n", " ")
    if len(deck) > max_summary:
        deck = deck[: max_summary - 1].rstrip() + "…"

    powers = _names(character.get("powers"))
    teams = _names(character.get("teams"))
    real_name = character.get("real_name")

    card = {
        "id": character["id"],
        "name": character["name"],
        "real_name": real_name,
        "summary": deck,
        "powers": powers,
        "teams": teams,
        "issue_appearances": character.get("count_of_issue_appearances"),
    }
    return {k: v for k, v in card.items() if v not in (None, "", [])}


def card_text(card: dict) -> str:
    """Flatten a fighter card for SemIf string state."""
    lines = [f"Name: {card['name']}"]
    if card.get("real_name"):
        lines.append(f"Real name: {card['real_name']}")
    if card.get("summary"):
        lines.append(f"Summary: {card['summary']}")
    if card.get("powers"):
        lines.append("Powers: " + ", ".join(card["powers"]))
    if card.get("teams"):
        lines.append("Teams: " + ", ".join(card["teams"]))
    if card.get("issue_appearances") is not None:
        lines.append(f"Issue appearances: {card['issue_appearances']}")
    return "\n".join(lines)
