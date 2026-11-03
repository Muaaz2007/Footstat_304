"""Query helpers used by the API layer.

Everything the dashboard needs to ask is expressed here as a plain function:
search, filter, sort, paginate and summarise. Keeping these queries out of the
HTTP handler means the logic can be unit-tested directly, without starting a
server.

All queries work on the in-memory dataset produced by ``backend.data.loader``.
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .loader import EVALUATIONS, POSITION_GROUPS, PlayerDataset

#: Columns a caller is allowed to sort by. Anything else is rejected so a typo
#: does not silently return unsorted data.
SORTABLE_COLUMNS = (
    "player_id",
    "name",
    "age",
    "nationality",
    "position_group",
    "overall_rating",
    "potential",
    "actual_value_eur",
    "predicted_value_eur",
    "value_difference_eur",
    "relative_difference",
    "evaluation",
)

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class QueryError(ValueError):
    """The caller asked for something invalid (bad sort column, huge limit...)."""


def _search_haystack(player: Dict[str, Any]) -> str:
    parts = (
        player.get("name"),
        player.get("full_name"),
        player.get("nationality"),
        player.get("positions"),
        player.get("position_group"),
    )
    return " ".join(str(part) for part in parts if part).lower()


def matches_search(player: Dict[str, Any], terms: Sequence[str]) -> bool:
    """Every search word must appear somewhere in the player's text fields."""
    haystack = _search_haystack(player)
    return all(term in haystack for term in terms)


def _split_search(search: Optional[str]) -> List[str]:
    if not search:
        return []
    return [token for token in search.lower().split() if token]


def _sorted(players: List[Dict[str, Any]], column: str, descending: bool) -> List[Dict[str, Any]]:
    """Sort with missing values always last, whatever the direction."""
    present = [player for player in players if player.get(column) is not None]
    missing = [player for player in players if player.get(column) is None]

    def key(player: Dict[str, Any]):
        value = player[column]
        return value.lower() if isinstance(value, str) else value

    present.sort(key=key, reverse=descending)
    return present + missing


def query_players(
    dataset: PlayerDataset,
    *,
    search: Optional[str] = None,
    position_group: Optional[str] = None,
    evaluation: Optional[str] = None,
    sort: str = "player_id",
    order: str = "asc",
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> Dict[str, Any]:
    """Filter, sort and paginate the players. Returns a response-shaped dict."""
    if sort not in SORTABLE_COLUMNS:
        raise QueryError(
            f"Unknown sort column {sort!r}. Allowed: {', '.join(SORTABLE_COLUMNS)}"
        )
    if order not in ("asc", "desc"):
        raise QueryError("order must be 'asc' or 'desc'")
    if position_group is not None and position_group not in POSITION_GROUPS:
        raise QueryError(
            f"Unknown position_group {position_group!r}. Allowed: {', '.join(POSITION_GROUPS)}"
        )
    if evaluation is not None and evaluation not in EVALUATIONS:
        raise QueryError(
            f"Unknown evaluation {evaluation!r}. Allowed: {', '.join(EVALUATIONS)}"
        )
    if limit < 1 or limit > MAX_LIMIT:
        raise QueryError(f"limit must be between 1 and {MAX_LIMIT}")
    if offset < 0:
        raise QueryError("offset must be zero or greater")

    terms = _split_search(search)
    selected: List[Dict[str, Any]] = []
    for player in dataset.players:
        if position_group is not None and player["position_group"] != position_group:
            continue
        if evaluation is not None and player["evaluation"] != evaluation:
            continue
        if terms and not matches_search(player, terms):
            continue
        selected.append(player)

    selected = _sorted(selected, sort, descending=(order == "desc"))
    total = len(selected)
    window = selected[offset : offset + limit]

    return {
        "total": total,
        "count": len(window),
        "limit": limit,
        "offset": offset,
        "results": window,
    }


def lookup_by_name(
    dataset: PlayerDataset, name: str, birth_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Find players by short or full name, optionally narrowed by birth date.

    The interface document warns that short names are not unique, so this
    returns every match rather than guessing which player the caller meant.
    """
    wanted = (name or "").strip().lower()
    if not wanted:
        raise QueryError("name must not be empty")

    found = [
        player
        for player in dataset.players
        if wanted == (player.get("name") or "").lower()
        or wanted == (player.get("full_name") or "").lower()
        or wanted in (player.get("full_name") or "").lower()
    ]
    if birth_date:
        found = [player for player in found if player.get("birth_date") == birth_date]
    return found


def _money_mean(values: Iterable[Optional[float]]) -> Optional[float]:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return round(sum(clean) / len(clean), 2)


def summarize(dataset: PlayerDataset, *, top_n: int = 5) -> Dict[str, Any]:
    """Headline numbers for the dashboard overview page."""
    players = dataset.players

    with_value = [player for player in players if player["actual_value_eur"] is not None]
    without_value = [player for player in players if player["actual_value_eur"] is None]

    evaluation_counts = {label: 0 for label in EVALUATIONS}
    for player in players:
        evaluation_counts[player["evaluation"]] += 1

    group_counts = {group: 0 for group in POSITION_GROUPS}
    for player in players:
        group_counts[player["position_group"]] += 1

    abs_relative = [
        abs(player["relative_difference"])
        for player in with_value
        if player["relative_difference"] is not None
    ]

    def brief(player: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "player_id": player["player_id"],
            "name": player["name"],
            "position_group": player["position_group"],
            "actual_value_eur": player["actual_value_eur"],
            "predicted_value_eur": player["predicted_value_eur"],
            "relative_difference": player["relative_difference"],
        }

    ranked = [player for player in with_value if player["relative_difference"] is not None]
    by_relative = sorted(ranked, key=lambda player: player["relative_difference"], reverse=True)

    return {
        "total_players": len(players),
        "players_with_recorded_value": len(with_value),
        "players_without_recorded_value": len(without_value),
        "evaluation_counts": evaluation_counts,
        "position_group_counts": group_counts,
        "average_predicted_value_eur": _money_mean(
            player["predicted_value_eur"] for player in players
        ),
        "average_actual_value_eur": _money_mean(
            player["actual_value_eur"] for player in with_value
        ),
        "median_absolute_relative_difference": (
            round(statistics.median(abs_relative), 4) if abs_relative else None
        ),
        "most_undervalued": [brief(player) for player in by_relative[:top_n]],
        "most_overvalued": [brief(player) for player in by_relative[-top_n:][::-1]],
    }


def metadata(dataset: PlayerDataset) -> Dict[str, Any]:
    """Values the dashboard needs to build its filters and table columns."""
    return {
        "player_count": len(dataset),
        "position_groups": list(POSITION_GROUPS),
        "evaluations": list(EVALUATIONS),
        "sortable_columns": list(SORTABLE_COLUMNS),
        "max_limit": MAX_LIMIT,
        "default_limit": DEFAULT_LIMIT,
        "fields": {
            "player_id": "Unique player identifier (use this to look players up)",
            "name": "Short display name (not unique on its own)",
            "full_name": "Full player name",
            "birth_date": "Date of birth; use with name to disambiguate players",
            "age": "Age in the dataset",
            "nationality": "Player nationality",
            "positions": "List of positions from the dataset",
            "position_group": "GK / DEF / MID / FWD",
            "overall_rating": "Current overall rating",
            "potential": "Potential rating",
            "actual_value_eur": "Recorded market value; empty when not recorded",
            "predicted_value_eur": "AI estimate of market value in euros",
            "value_difference_eur": "predicted - recorded value",
            "relative_difference": "(predicted - recorded) / recorded",
            "evaluation": "Potentially Undervalued / Fairly Valued / Potentially Overvalued / No recorded value",
            "prediction_type": "out-of-fold (5-fold CV) or final model",
        },
    }
