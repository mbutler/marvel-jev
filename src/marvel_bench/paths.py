from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DEFAULT_CHARACTERS = DATA_DIR / "characters.json"
SAMPLE_CHARACTERS = DATA_DIR / "sample_characters.json"
DEFAULT_FIGHTS = DATA_DIR / "fights.jsonl"
DEFAULT_RESULTS = DATA_DIR / "results.jsonl"
DEFAULT_LEADERBOARD = DATA_DIR / "leaderboard.json"
DEFAULT_REPORT = DATA_DIR / "report.json"

MARVEL_PUBLISHER_ID = 31
COMIC_VINE_BASE = "https://comicvine.gamespot.com/api"
OPENROUTER_SYSTEMONE_URL = "https://openrouter.ai/api/v1/systemone"
DEFAULT_OPENROUTER_MODEL = "~typesafe/jev-latest"
DEFAULT_SEMIF_MODEL = "Qwen/Qwen3.5-4B"
DEFAULT_SEMIF_REVISION = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"


def load_env() -> None:
    load_dotenv(ROOT / ".env")


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def resolve_characters_path(path: Path | None = None, *, prefer_sample: bool = False) -> Path:
    if path is not None:
        return path
    if prefer_sample or not DEFAULT_CHARACTERS.exists():
        return SAMPLE_CHARACTERS
    return DEFAULT_CHARACTERS


def load_characters(path: Path | None = None) -> list[dict]:
    resolved = resolve_characters_path(path)
    with resolved.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected a list of characters in {resolved}")
    return data


def write_json(path: Path, payload: object) -> None:
    ensure_data_dir()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    ensure_data_dir()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_no}") from exc
    return rows


def append_jsonl(path: Path, row: dict) -> None:
    ensure_data_dir()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value
