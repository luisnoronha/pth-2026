"""`hackrex-local`: the whole Hack Rex game on your laptop, stdlib HTTP only.

  /             attack page (phones)          /scoreboard   big screen
  /admin        approve snippets, kill switch /p/<id>.html  poisoned pages Rex reads
  /api/...      the same API the Lambda serves (see api.py)

Runs on localhost:8000 so the poisoned pages are already on Rex's allowlist.
Rex runs in a small thread pool: extra attacks wait in line, like on Lambda.
"""

import argparse
import json
import logging
import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from leash.common.config import model_names, model_settings
from leash.hackrex.api import Api, RateLimiter
from leash.hackrex.gate import Gate, LocalPageHost
from leash.hackrex.store import AttemptStore
from leash.rex.offline import gullible_model

REPO = Path(__file__).resolve().parents[4]
WEB = REPO / "frontend" / "web"
PAGES = {"/": "index.html", "/scoreboard": "scoreboard.html", "/admin": "admin.html"}
PAGES.update({f"/{name}": name for name in list(PAGES.values())})
RATE_PER_MINUTE = int(os.getenv("HACKREX_RATE_PER_MINUTE", "5"))
CONFIG_JS = b'window.HACKREX_API = "";\n'  # same origin locally


def make_handler(api: Api, pages_folder: Path, web: Path = WEB):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            logging.getLogger("leash.hackrex").debug(fmt, *args)

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _api(self, method: str) -> None:
            length = min(int(self.headers.get("Content-Length") or 0), 64_000)
            code, payload = api.handle(method, self.path.split("?")[0], dict(self.headers), self.rfile.read(length))
            body = b"" if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send(code, body, "application/json")

        def do_GET(self):
            path = self.path.split("?")[0]
            if path.startswith("/api/"):
                return self._api("GET")
            if path in PAGES:
                return self._send(200, (web / PAGES[path]).read_bytes(), "text/html; charset=utf-8")
            if path == "/config.js":
                return self._send(200, CONFIG_JS, "application/javascript")
            if path.startswith("/p/") and path.endswith(".html"):
                page = pages_folder / Path(path).name  # Path.name drops any ../
                if page.exists():
                    return self._send(200, page.read_bytes(), "text/html; charset=utf-8")
            self._send(404, b'{"error": "not found"}', "application/json")

        def do_POST(self):
            self._api("POST")

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(prog="hackrex-local", description="Run Hack Rex on this laptop.")
    parser.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to let phones on your wifi in")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--offline", action="store_true", help="gullible scripted brain instead of a real model")
    parser.add_argument("--model", choices=model_names(), help="model name from rex.yaml (default: its `active`)")
    parser.add_argument("--workers", type=int, default=4, help="Rex runs at the same time; the rest wait in line")
    parser.add_argument("--data", type=Path, default=REPO / "scripts" / ".hackrex", help="attempts + pages folder")
    args = parser.parse_args()

    if args.model:
        os.environ["REX_MODEL"] = args.model
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    args.data.mkdir(parents=True, exist_ok=True)
    pages = LocalPageHost(args.data / "pages", f"http://localhost:{args.port}/p")
    gate = Gate(AttemptStore(args.data / "attempts.json"), pages,
                make_model=gullible_model if args.offline else (lambda: None))
    pool = ThreadPoolExecutor(max_workers=args.workers)
    admin_token = os.getenv("HACKREX_ADMIN_TOKEN") or secrets.token_urlsafe(8)
    api = Api(gate, admin_token, RateLimiter(RATE_PER_MINUTE),
              start_run=lambda attempt_id: pool.submit(gate.run, attempt_id))

    server = ThreadingHTTPServer((args.host, args.port), make_handler(api, pages.folder))
    brain = "offline (gullible brain)" if args.offline else f"model {model_settings().name}"
    print(f"Hack Rex on http://localhost:{args.port}  ({brain}, leash level 5)")
    print(f"  scoreboard: http://localhost:{args.port}/scoreboard")
    print(f"  admin:      http://localhost:{args.port}/admin   token: {admin_token}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        pool.shutdown(wait=False, cancel_futures=True)


if __name__ == "__main__":
    main()
