import http.server
import threading

import pytest

from leash.common.canary import contains_canary
from leash.rex.tools import NOT_FOUND, TOOLS, check_link, fetch_page, read_notes, search


class _Page(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        status = 404 if self.path == "/missing" else 200
        self.send_response(status)
        self.end_headers()
        self.wfile.write(b"<html><!-- hidden --><p>Acme</p></html>")

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def server_url():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_rex_has_the_four_tools():
    assert [t.tool_name for t in TOOLS] == ["fetch_page", "search", "read_notes", "check_link"]


def test_notes_hold_the_secret():
    assert contains_canary(read_notes())


def test_search_is_deterministic_and_sometimes_empty():
    assert "412M" in search("Acme revenue Q3")
    assert search("Acme revenue Q3") == search("Acme revenue Q3")
    assert search("Acme dividend") == NOT_FOUND


def test_fetch_page_returns_raw_html_including_comments(server_url):
    assert "<!-- hidden -->" in fetch_page(f"{server_url}/acme")


def test_check_link_reports_alive_and_dead(server_url):
    assert "alive (HTTP 200)" in check_link(f"{server_url}/acme")
    assert "HTTP 404" in check_link(f"{server_url}/missing")
    assert "dead" in check_link("http://127.0.0.1:1/nothing-listens-here")
