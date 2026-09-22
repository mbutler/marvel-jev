from __future__ import annotations

import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from marvel_bench.paths import (
    DATA_DIR,
    DEFAULT_LEADERBOARD,
    DEFAULT_REPORT,
    DEFAULT_RESULTS,
    SAMPLE_CHARACTERS,
    ensure_data_dir,
    resolve_characters_path,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


class ResultsHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/report":
            return self._send_json_file(DEFAULT_REPORT)
        if parsed.path == "/api/leaderboard":
            return self._send_json_file(DEFAULT_LEADERBOARD)
        if parsed.path == "/api/results":
            return self._send_jsonl_as_json(DEFAULT_RESULTS)
        if parsed.path == "/api/characters":
            path = resolve_characters_path()
            return self._send_json_file(path if path.exists() else SAMPLE_CHARACTERS)
        if parsed.path in ("/", "/index.html"):
            return self._send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
        return super().do_GET()

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(404, "Not found")
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_json_file(self, path: Path) -> None:
        if not path.exists():
            payload = {"error": f"Missing {path.name}. Run marvel-bench report first."}
            body = json.dumps(payload).encode()
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._send_file(path, "application/json; charset=utf-8")

    def _send_jsonl_as_json(self, path: Path) -> None:
        rows = []
        if path.exists():
            with path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
        body = json.dumps(rows).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        # Quieter default logging
        if args and str(args[0]).startswith("GET /api/"):
            return
        super().log_message(format, *args)


def serve_results(*, host: str = "127.0.0.1", port: int = 8765) -> None:
    ensure_data_dir()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    handler = partial(ResultsHandler)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Results UI: http://{host}:{port}")
    print("API: /api/report /api/leaderboard /api/results /api/characters")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()
