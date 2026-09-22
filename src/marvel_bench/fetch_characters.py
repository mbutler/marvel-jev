from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from marvel_bench.paths import (
    COMIC_VINE_BASE,
    DEFAULT_CHARACTERS,
    MARVEL_PUBLISHER_ID,
    ensure_data_dir,
    require_env,
    write_json,
)


class RateLimiter:
    """Simple spacing between Comic Vine requests."""

    def __init__(self, min_interval_s: float = 1.5) -> None:
        self.min_interval_s = min_interval_s
        self._last = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        delay = self.min_interval_s - (now - self._last)
        if delay > 0:
            time.sleep(delay)
        self._last = time.monotonic()


def _normalize_character(raw: dict[str, Any]) -> dict[str, Any]:
    publisher = raw.get("publisher") or {}
    powers = raw.get("powers") or []
    teams = raw.get("teams") or []
    return {
        "id": raw["id"],
        "name": raw.get("name") or f"character-{raw['id']}",
        "real_name": raw.get("real_name"),
        "deck": raw.get("deck"),
        "publisher": {
            "id": publisher.get("id"),
            "name": publisher.get("name"),
        }
        if publisher
        else None,
        "powers": [
            {"id": p.get("id"), "name": p.get("name")}
            for p in powers
            if isinstance(p, dict) and p.get("name")
        ],
        "teams": [
            {"id": t.get("id"), "name": t.get("name")}
            for t in teams
            if isinstance(t, dict) and t.get("name")
        ],
        "count_of_issue_appearances": raw.get("count_of_issue_appearances") or 0,
        "image": (raw.get("image") or {}).get("thumb_url") if raw.get("image") else None,
        "site_detail_url": raw.get("site_detail_url"),
    }


def _is_marvel(raw: dict[str, Any], publisher_id: int) -> bool:
    pub = raw.get("publisher") or {}
    return pub.get("id") == publisher_id


def fetch_marvel_characters(
    *,
    api_key: str | None = None,
    limit: int | None = None,
    page_size: int = 100,
    publisher_id: int = MARVEL_PUBLISHER_ID,
    user_agent: str | None = None,
    min_interval_s: float = 1.5,
    out_path: Path = DEFAULT_CHARACTERS,
    max_scan: int | None = None,
) -> list[dict[str, Any]]:
    """Collect Marvel characters ranked by issue appearances.

    Comic Vine's ``filter=publisher:…`` on ``/characters/`` is unreliable (returns
    mixed publishers). We paginate globally by ``count_of_issue_appearances`` and
    keep rows whose ``publisher.id`` equals Marvel (31). Absolute Marvel count on
    Comic Vine is available via ``GET /publisher/31/`` (~23k character refs).
    """
    key = api_key or require_env("COMIC_VINE_API_KEY")
    ua = user_agent or require_env_optional_ua()
    limiter = RateLimiter(min_interval_s=min_interval_s)
    field_list = (
        "id,name,real_name,deck,publisher,powers,teams,"
        "count_of_issue_appearances,image,site_detail_url"
    )

    # Overscan: Comic Vine's appearance sort is noisy, so early pages mix in
    # low-appearance rows. Collect a larger Marvel pool, then keep the true top N.
    if max_scan is None:
        if limit is None:
            max_scan = 50_000
        else:
            max_scan = max(limit * 20, 4_000)

    target_pool = None if limit is None else max(limit * 3, limit + 200)

    characters: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    offset = 0
    scanned = 0
    pages = 0

    headers = {"User-Agent": ua}
    print(
        f"Scanning Comic Vine by appearances; keeping publisher.id=={publisher_id} "
        f"(keep_top={limit or 'all'}, pool_target={target_pool or '—'}, max_scan={max_scan})"
    )

    with httpx.Client(timeout=60.0, headers=headers, follow_redirects=True) as client:
        while True:
            if target_pool is not None and len(characters) >= target_pool and scanned >= max(limit or 0, 1000):
                # Have a fat enough pool after a meaningful scan window
                if scanned >= min(max_scan, max((limit or 0) * 12, 3000)):
                    break
            if scanned >= max_scan:
                print(f"Stopped at max_scan={max_scan} with {len(characters)} Marvel characters")
                break

            params = {
                "api_key": key,
                "format": "json",
                "limit": page_size,
                "offset": offset,
                "field_list": field_list,
                "sort": "count_of_issue_appearances:desc",
            }
            limiter.wait()
            resp = client.get(f"{COMIC_VINE_BASE}/characters/", params=params)
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("error") not in (None, "OK"):
                raise RuntimeError(f"Comic Vine error: {payload.get('error')}")

            results = payload.get("results") or []
            if not results:
                break

            pages += 1
            scanned += len(results)
            for raw in results:
                if not _is_marvel(raw, publisher_id):
                    continue
                cid = int(raw["id"])
                if cid in seen_ids:
                    continue
                seen_ids.add(cid)
                characters.append(_normalize_character(raw))

            offset += len(results)
            print(
                f"page={pages} scanned={scanned} marvel_pool={len(characters)}"
                + (f" (need ~{target_pool})" if target_pool else "")
            )

            if target_pool is not None and len(characters) >= target_pool and scanned >= max((limit or 0) * 12, 3000):
                break

    characters.sort(
        key=lambda c: (-(c.get("count_of_issue_appearances") or 0), c["name"])
    )
    if limit is not None:
        characters = characters[:limit]

    ensure_data_dir()
    write_json(out_path, characters)
    if characters:
        print(
            f"Wrote {len(characters)} Marvel characters to {out_path} "
            f"(apps {characters[-1]['count_of_issue_appearances']}–"
            f"{characters[0]['count_of_issue_appearances']})"
        )
    else:
        print(f"Wrote 0 characters to {out_path}")
    return characters


def require_env_optional_ua() -> str:
    import os

    return os.getenv(
        "COMIC_VINE_USER_AGENT",
        "MarvelBench/0.1 (personal research; https://github.com/local/marvel-bench)",
    )
