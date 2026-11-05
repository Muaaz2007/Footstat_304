"""Thin client for the Footstat_304 backend API.

One place for the base URL, the timeouts and the error handling, so every page
imports the same behaviour. Nothing here loads the model or trains anything.

    FOOTSTAT_API   override the base URL (default http://127.0.0.1:8000)
"""

from __future__ import annotations

import os

import requests

API = os.environ.get("FOOTSTAT_API", "http://127.0.0.1:8000")
TIMEOUT = 15

# Used only when /api/meta cannot be reached, so the dashboard still renders.
# Keep in step with backend/data/queries.py: metadata().
FALLBACK_META = {
    "player_count": 17954,
    "default_limit": 50,
    "max_limit": 200,
    "position_groups": ["DEF", "FWD", "GK", "MID"],
    "evaluations": [
        "Potentially Undervalued",
        "Fairly Valued",
        "Potentially Overvalued",
        "No recorded value",
    ],
    "sortable_columns": [
        "player_id", "name", "age", "nationality", "position_group", "overall_rating",
        "potential", "actual_value_eur", "predicted_value_eur", "value_difference_eur",
        "relative_difference", "evaluation",
    ],
    "fields": [
        "player_id", "name", "full_name", "age", "birth_date", "nationality", "positions",
        "position_group", "overall_rating", "potential", "actual_value_eur",
        "predicted_value_eur", "value_difference_eur", "relative_difference",
        "evaluation", "prediction_type",
    ],
}


class ApiError(RuntimeError):
    """The backend answered with an error, or could not be reached."""


def _url(path: str) -> str:
    return f"{API.rstrip('/')}{path}"


def _get(path: str, **params):
    params = {k: v for k, v in params.items() if v is not None}
    try:
        response = requests.get(_url(path), params=params, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise ApiError(
            f"Cannot reach the API at {API}. Start it with "
            "`python -m backend.api --port 8000`."
        ) from exc
    if not response.ok:
        try:
            detail = response.json().get("error", {}).get("message", response.text)
        except ValueError:
            detail = response.text
        raise ApiError(f"{response.status_code}: {detail}")
    return response.json()


def _post(path: str, payload: dict, timeout: int = 60):
    try:
        response = requests.post(_url(path), json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise ApiError(f"Cannot reach the API at {API}.") from exc
    if not response.ok:
        try:
            detail = response.json().get("error", {}).get("message", response.text)
        except ValueError:
            detail = response.text
        raise ApiError(f"{response.status_code}: {detail}")
    return response.json()


def health():
    return _get("/api/health")


def meta():
    return _get("/api/meta")


def is_up() -> bool:
    """True when the backend answers, without raising."""
    try:
        return health().get("status") == "ok"
    except ApiError:
        return False


def summary():
    return _get("/api/summary")


def players(**params):
    return _get("/api/players", **params)


def player(player_id: int):
    return _get(f"/api/players/{int(player_id)}")


def lookup(name: str):
    return _get("/api/players/lookup", name=name)


def all_players(page_size: int = 200) -> list[dict]:
    """Every row of the prediction table, page by page.

    The API caps ``limit`` at ``meta["max_limit"]`` (200), so 17,954 players take
    90 requests. Call it once, cache the result, and filter locally.
    """
    rows: list[dict] = []
    while True:
        page = _get(
            "/api/players", sort="player_id", order="asc",
            limit=page_size, offset=len(rows),
        )
        rows.extend(page["results"])
        if not page.get("count") or len(rows) >= page.get("total", len(rows)):
            return rows


def predict(features: dict, actual_value_eur: float | None = None):
    body = {"features": features}
    if actual_value_eur is not None:
        body["actual_value_eur"] = actual_value_eur
    return _post("/api/predict", body)["prediction"]
