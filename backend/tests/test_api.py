"""Tests for the HTTP API, run against a real server on an ephemeral port."""
from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.api import make_server  # noqa: E402


class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        # keep the test output readable
        cls.server.RequestHandlerClass.log_message = lambda *args, **kwargs: None
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def get(self, path: str):
        url = f"http://127.0.0.1:{self.port}{path}"
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                body = json.loads(response.read().decode("utf-8"))
                return response.status, body, dict(response.headers)
        except urllib.error.HTTPError as error:
            body = json.loads(error.read().decode("utf-8"))
            return error.code, body, dict(error.headers)

    def test_index_lists_endpoints(self):
        status, body, _ = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("endpoints", body)
        self.assertIn("GET /api/players/{player_id}", body["endpoints"])

    def test_health(self):
        status, body, _ = self.get("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["players"], 17954)

    def test_meta(self):
        status, body, _ = self.get("/api/meta")
        self.assertEqual(status, 200)
        self.assertIn("Potentially Undervalued", body["evaluations"])

    def test_summary(self):
        status, body, _ = self.get("/api/summary")
        self.assertEqual(status, 200)
        self.assertEqual(sum(body["evaluation_counts"].values()), body["total_players"])

    def test_player_list_respects_limit(self):
        status, body, _ = self.get("/api/players?limit=3")
        self.assertEqual(status, 200)
        self.assertEqual(body["count"], 3)
        self.assertEqual(body["limit"], 3)
        self.assertGreater(body["total"], 3)

    def test_player_list_filters(self):
        status, body, _ = self.get("/api/players?position_group=GK&limit=5")
        self.assertEqual(status, 200)
        self.assertTrue(all(p["position_group"] == "GK" for p in body["results"]))

    def test_single_player(self):
        status, body, _ = self.get("/api/players/1")
        self.assertEqual(status, 200)
        self.assertEqual(body["player_id"], 1)
        self.assertEqual(body["name"], "L. Messi")

    def test_unknown_player_returns_404(self):
        status, body, _ = self.get("/api/players/999999")
        self.assertEqual(status, 404)
        self.assertIn("message", body["error"])

    def test_non_numeric_player_id_returns_400(self):
        status, body, _ = self.get("/api/players/abc")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "bad_request")

    def test_limit_above_maximum_returns_400(self):
        status, body, _ = self.get("/api/players?limit=1000")
        self.assertEqual(status, 400)
        self.assertIn("limit", body["error"]["message"])

    def test_bad_sort_column_returns_400(self):
        status, body, _ = self.get("/api/players?sort=wage")
        self.assertEqual(status, 400)
        self.assertIn("sort", body["error"]["message"].lower())

    def test_lookup_by_name(self):
        status, body, _ = self.get("/api/players/lookup?name=Messi")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(body["count"], 1)

    def test_lookup_without_name_returns_400(self):
        status, body, _ = self.get("/api/players/lookup")
        self.assertEqual(status, 400)

    def test_unknown_route_returns_404(self):
        status, body, _ = self.get("/api/nope")
        self.assertEqual(status, 404)
        self.assertIn("No route", body["error"]["message"])

    def test_cors_header_allows_the_dashboard(self):
        _, _, headers = self.get("/api/health")
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "*")
        self.assertEqual(headers.get("Content-Type"), "application/json; charset=utf-8")


if __name__ == "__main__":
    unittest.main()
