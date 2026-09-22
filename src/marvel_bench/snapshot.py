from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from marvel_bench.paths import (
    DEFAULT_LEADERBOARD,
    DEFAULT_REPORT,
    DEFAULT_RESULTS,
    ROOT,
    ensure_data_dir,
    read_jsonl,
)

STATIC_TEMPLATE = Path(__file__).resolve().parent / "static" / "index.html"
DEFAULT_SNAPSHOT = ROOT / "snapshot" / "index.html"

FIGHT_KEYS = (
    "id",
    "a_name",
    "b_name",
    "choice",
    "probabilities",
    "winner_name",
    "latency_ms",
    "backend",
    "error",
)


def _compact_fight(row: dict) -> dict:
    return {k: row[k] for k in FIGHT_KEYS if k in row and row[k] is not None}


def build_snapshot(
    *,
    results_path: Path = DEFAULT_RESULTS,
    report_path: Path = DEFAULT_REPORT,
    leaderboard_path: Path = DEFAULT_LEADERBOARD,
    out_path: Path = DEFAULT_SNAPSHOT,
    max_fights: int | None = None,
) -> Path:
    """Write a self-contained HTML file that needs no server."""
    if not report_path.exists() or not leaderboard_path.exists():
        raise SystemExit("Missing report/leaderboard. Run `marvel-bench report` first.")
    if not results_path.exists():
        raise SystemExit(f"Missing results at {results_path}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    leaderboard = json.loads(leaderboard_path.read_text(encoding="utf-8"))
    results = [_compact_fight(r) for r in read_jsonl(results_path)]
    if max_fights is not None:
        results = results[-max_fights:]

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "report": report,
        "leaderboard": leaderboard,
        "results": results,
    }

    template = STATIC_TEMPLATE.read_text(encoding="utf-8")
    # Swap live API loader for embedded snapshot data.
    old_script_start = "  <script>\n    const state = { report: null, leaderboard: null, results: [], backend: null };"
    if old_script_start not in template:
        raise SystemExit("static/index.html shape changed; update snapshot builder")

    data_js = (
        "  <script>\n"
        f"    window.__SNAPSHOT__ = {json.dumps(payload, separators=(',', ':'))};\n"
        "    const state = { report: null, leaderboard: null, results: [], backend: null };"
    )
    html = template.replace(old_script_start, data_js, 1)

    old_load = """    async function load() {
      try {
        const [report, leaderboard, results] = await Promise.all([
          fetch("/api/report").then(r => r.json()),
          fetch("/api/leaderboard").then(r => r.json()),
          fetch("/api/results").then(r => r.json()),
        ]);
        if (report.error) throw new Error(report.error);
        state.report = report;
        state.leaderboard = leaderboard;
        state.results = Array.isArray(results) ? results.slice().reverse() : [];
        const backends = Object.keys(report.backends || {});
        state.backend = backends[0] || null;
        renderStats();
        fillBackendSelect(backends);
        renderLeaderboard();
        renderFights();
      } catch (err) {
        document.getElementById("stats").innerHTML =
          `<div class="error">${err.message}<br/><span class="muted">Run generate → score → report first.</span></div>`;
        document.getElementById("leaderboard").innerHTML = "";
        document.getElementById("fights").innerHTML = "";
      }
    }"""

    new_load = """    async function load() {
      try {
        const snap = window.__SNAPSHOT__;
        if (!snap || !snap.report) throw new Error("Snapshot data missing.");
        state.report = snap.report;
        state.leaderboard = snap.leaderboard;
        state.results = Array.isArray(snap.results) ? snap.results.slice().reverse() : [];
        const backends = Object.keys(snap.report.backends || {});
        state.backend = backends[0] || null;
        const when = snap.generated_at ? ` Snapshot ${snap.generated_at}.` : "";
        const sub = document.querySelector(".sub");
        if (sub && when && !sub.textContent.includes("Snapshot")) {
          sub.textContent = sub.textContent.trim() + when;
        }
        renderStats();
        fillBackendSelect(backends);
        renderLeaderboard();
        renderFights();
      } catch (err) {
        document.getElementById("stats").innerHTML =
          `<div class="error">${err.message}</div>`;
        document.getElementById("leaderboard").innerHTML = "";
        document.getElementById("fights").innerHTML = "";
      }
    }"""

    if old_load not in html:
        raise SystemExit("Could not patch load() for snapshot; template mismatch")
    html = html.replace(old_load, new_load, 1)
    html = html.replace(
        "<title>Marvel Matchup Bench</title>",
        "<title>Marvel Matchup Bench (snapshot)</title>",
        1,
    )

    ensure_data_dir()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    mb = out_path.stat().st_size / (1024 * 1024)
    print(f"Wrote static snapshot ({mb:.1f} MB, {len(results)} fights) -> {out_path}")
    print("Open that file in a browser — no server needed.")
    return out_path
