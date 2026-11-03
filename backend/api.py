"""HTTP API for the dashboard.

The dashboard only needs three things from the backend: a summary of the
dataset, a searchable list of players, and a single player's full evaluation.
This module exposes exactly those, using Python's standard library HTTP server
so the whole backend runs with ``python -m backend.api`` and no extra installs.

Architecture note: this is the *runtime* side of the system described in the
architecture document (User -> Dashboard -> player selection -> prediction
table -> player results -> User). It never trains a model; it reads the table
the AI subsystem produced.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, unquote, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.loader import (  # noqa: E402
    DataFileNotFound,
    PlayerDataset,
    SchemaError,
    load_dataset,
)
from backend.data.queries import (  # noqa: E402
    DEFAULT_LIMIT,
    MAX_LIMIT,
    QueryError,
    lookup_by_name,
    metadata,
    query_players,
    summarize,
)

API_VERSION = "0.1"


def _param(params: Dict[str, list], name: str) -> Optional[str]:
    values = params.get(name)
    if not values:
        return None
    value = values[0].strip()
    return value or None


def _int_param(params: Dict[str, list], name: str, default: int) -> int:
    raw = _param(params, name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise QueryError(f"{name} must be a whole number") from exc


class PlayerRequestHandler(BaseHTTPRequestHandler):
    """Routes requests to the query functions and returns JSON."""

    dataset: PlayerDataset
    server_version = "Footstat304Backend/" + API_VERSION

    # -- helpers ---------------------------------------------------------
    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str, code: Optional[str] = None) -> None:
        self._send_json(status, {"error": {"status": status, "code": code, "message": message}})

    # -- HTTP verbs ------------------------------------------------------
    def do_OPTIONS(self) -> None:  # noqa: N802 - name required by the base class
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 - name required by the base class
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)

        try:
            if path in ("/", "/api"):
                self._send_json(200, self._index())
            elif path == "/api/health":
                self._send_json(200, self._health())
            elif path == "/api/meta":
                self._send_json(200, metadata(self.dataset))
            elif path == "/api/summary":
                self._send_json(200, summarize(self.dataset))
            elif path == "/api/players":
                self._send_json(200, self._players(params))
            elif path == "/api/players/lookup":
                self._send_json(200, self._lookup(params))
            elif path.startswith("/api/players/"):
                self._send_json(200, self._one_player(path.rsplit("/", 1)[-1]))
            else:
                self._send_error(404, f"No route for {path}")

        except QueryError as exc:
            self._send_error(400, str(exc), "bad_request")
        except LookupError as exc:
            self._send_error(404, str(exc), "not_found")
        except DataFileNotFound as exc:
            self._send_error(503, str(exc), "data_unavailable")
        except SchemaError as exc:
            self._send_error(500, str(exc), "data_schema")
        except BrokenPipeError:
            pass  # client went away; nothing useful to do
        except Exception as exc:  # noqa: BLE001 - last resort so one request cannot kill the server
            self.log_error("unhandled error: %r", exc)
            self._send_error(500, "Unexpected server error", "internal_error")

    # -- route implementations -------------------------------------------
    def _index(self) -> Dict[str, Any]:
        return {
            "name": "Footstat_304 backend API",
            "version": API_VERSION,
            "description": "Player market-value evaluations produced by the AI subsystem.",
            "endpoints": {
                "GET /api/health": "service and data status",
                "GET /api/meta": "filter values, sortable columns and field meanings",
                "GET /api/summary": "dataset totals, evaluation counts and top movers",
                "GET /api/players": (
                    "searchable player list; query: search, position_group, evaluation, "
                    f"sort, order, limit (max {MAX_LIMIT}), offset"
                ),
                "GET /api/players/{player_id}": "one player's full evaluation",
                "GET /api/players/lookup?name=&birth_date=": "find players by name",
            },
        }

    def _health(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "players": len(self.dataset),
            "source": str(self.dataset.source_path),
        }

    def _players(self, params: Dict[str, list]) -> Dict[str, Any]:
        return query_players(
            self.dataset,
            search=_param(params, "search"),
            position_group=_param(params, "position_group"),
            evaluation=_param(params, "evaluation"),
            sort=_param(params, "sort") or "player_id",
            order=(_param(params, "order") or "asc").lower(),
            limit=_int_param(params, "limit", DEFAULT_LIMIT),
            offset=_int_param(params, "offset", 0),
        )

    def _one_player(self, raw_id: str) -> Dict[str, Any]:
        try:
            player_id = int(unquote(raw_id))
        except ValueError as exc:
            raise QueryError("player_id must be a whole number") from exc

        player = self.dataset.get(player_id)
        if player is None:
            raise LookupError(f"No player with player_id={player_id}")
        return player

    def _lookup(self, params: Dict[str, list]) -> Dict[str, Any]:
        name = _param(params, "name")
        if name is None:
            raise QueryError("name is required, for example /api/players/lookup?name=Messi")
        matches = lookup_by_name(self.dataset, name, _param(params, "birth_date"))
        return {
            "count": len(matches),
            "note": "Short names are not unique; use player_id to pick one player.",
            "results": matches,
        }


def make_server(
    host: str = "127.0.0.1", port: int = 8000, data_path: Optional[Path] = None
) -> ThreadingHTTPServer:
    """Build a server that serves the prediction table at ``data_path``."""
    dataset = load_dataset(data_path)
    handler = type("BoundPlayerRequestHandler", (PlayerRequestHandler,), {"dataset": dataset})
    return ThreadingHTTPServer((host, port), handler)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Footstat_304 backend API")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        help="path to player_predictions.csv (default: ai-core/outputs/player_predictions.csv)",
    )
    args = parser.parse_args(argv)

    try:
        server = make_server(args.host, args.port, args.data)
    except (DataFileNotFound, SchemaError) as exc:
        print(f"Could not start the API:\n{exc}", file=sys.stderr)
        return 1

    host, port = server.server_address[0], server.server_address[1]
    print(f"Footstat_304 backend API listening on http://{host}:{port}")
    print(f"Data source: {server.RequestHandlerClass.dataset.source_path}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
