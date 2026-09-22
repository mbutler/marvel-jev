# Marvel Matchup Bench

Pairwise Marvel character fights scored by **OpenRouter Jev** ([`~typesafe/jev-latest`](https://openrouter.ai/~typesafe/jev-latest)) and/or local **[SemIf](https://github.com/TheoLeeCJ/SemIf)** (open logit readout on Apple Silicon).

This repo does **not** use Marvel’s retired developer API. Character data comes from [Comic Vine](https://comicvine.gamespot.com/api/) (non-commercial; cache locally; credit them). A bundled sample roster lets you smoke-test without any keys.

## Setup

```bash
cd marvel
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Put keys in `.env` (never commit them):

```bash
OPENROUTER_API_KEY=sk-or-...
COMIC_VINE_API_KEY=...          # only needed for fetch
```

**Public repo reminder:** only `.env.example` (empty values) belongs in git. Real keys stay in local `.env`, which is gitignored. Generated Comic Vine caches and score outputs under `data/` are also ignored.

### Optional: SemIf (local throughput)

```bash
git clone https://github.com/TheoLeeCJ/SemIf.git ~/SemIf
cd ~/SemIf && pip install -e '.[test,mlx]'
# ensure `semif-score` is on PATH in the same venv
```

## Quick start (sample roster)

```bash
marvel-bench generate --sample --max-pairs 20
marvel-bench score --backend openrouter --limit 20
marvel-bench report
marvel-bench serve
```

Open http://127.0.0.1:8765

SemIf path (after install):

```bash
marvel-bench score --backend semif --limit 20
marvel-bench report
```

## Comic Vine roster (Marvel-only)

Comic Vine’s `filter=publisher:…` on `/characters/` is unreliable. Fetch scans by
issue appearances and **keeps `publisher.id == 31` (Marvel)** client-side. Absolute
Marvel count on Comic Vine is ~23k (`GET /publisher/31/`).

```bash
marvel-bench fetch --limit 250          # top Marvel by appearances (~$0.66 to score)
marvel-bench generate                   # all pairs for cached roster
marvel-bench score --backend openrouter --concurrency 8
marvel-bench report
```

Gates for experiments:

| Flag | Meaning |
|------|---------|
| `--limit` on `fetch` | Cap characters downloaded |
| `--limit-chars` on `generate` | Use top N by issue appearances |
| `--max-pairs` on `generate` | Cap fight jobs |
| `--limit` on `score` | Score first N fights only |

## Commands

| Command | Purpose |
|---------|---------|
| `fetch` | Paginate Marvel characters from Comic Vine → `data/characters.json` |
| `generate` | Emit `data/fights.jsonl` (backend-agnostic jobs) |
| `score --backend openrouter\|semif` | Append `data/results.jsonl` |
| `report` | Throughput, spend, win-rate leaderboard |
| `serve` | Local results UI (needs Python) |
| `snapshot` | Self-contained HTML you can open with no server |

## Cost note (OpenRouter)

Jev on OpenRouter is priced on **input** tokens (~$0.042/M). Roughly **~$42 per million fights** if each fight is ~1k input tokens. Watch cumulative `cost` in the report. Use SemIf when you want volume without spend.

## Data files

| Path | Role |
|------|------|
| `data/sample_characters.json` | Bundled smoke roster (committed) |
| `data/characters.json` | Comic Vine cache (gitignored) |
| `data/fights.jsonl` | Fight jobs |
| `data/results.jsonl` | Scored outcomes (tagged by `backend`) |
| `data/leaderboard.json` / `data/report.json` | Aggregates |

## Credits / constraints

- Character data © Comic Vine contributors; non-commercial use; link back; do not redistribute as a competing database.
- SemIf is independent research, not affiliated with TypeSafe/Jev.
- OpenRouter results are Jev via OpenRouter; SemIf results are an open-model stand-in.
