"""Data access layer for the player evaluation data.

This module reads the prediction table produced by the AI subsystem
(``ai-core/outputs/player_predictions.csv``) and gives the rest of the system
a clean, typed, validated view of it.

Why it is written this way
--------------------------
1. The architecture document separates *offline AI development* from the
   *runtime application*. The AI subsystem writes the prediction table once;
   the application reads it. This module is that read side.
2. Only the Python standard library is used (``csv``). The AI subsystem needs
   pandas and scikit-learn, but the dashboard-facing read path does not, so the
   backend does not force those heavy dependencies on whoever runs it.
3. The CSV is validated against an expected schema when it is loaded. If the AI
   side ever changes a column name, the backend fails with a clear message
   instead of silently showing wrong information.

The expected columns are the ones documented in
``ai-core/INTERFACE_FOR_DASHBOARD.md``.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

# Project root = two levels above this file (backend/data/loader.py).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PREDICTIONS_PATH = PROJECT_ROOT / "ai-core" / "outputs" / "player_predictions.csv"

#: Columns the backend depends on. Order matches the interface document.
REQUIRED_COLUMNS: Tuple[str, ...] = (
    "player_id",
    "name",
    "full_name",
    "birth_date",
    "age",
    "nationality",
    "positions",
    "position_group",
    "overall_rating",
    "potential",
    "actual_value_eur",
    "predicted_value_eur",
    "value_difference_eur",
    "relative_difference",
    "evaluation",
    "prediction_type",
)

INT_COLUMNS = ("player_id", "age", "overall_rating", "potential")
FLOAT_COLUMNS = (
    "actual_value_eur",
    "predicted_value_eur",
    "value_difference_eur",
    "relative_difference",
)
TEXT_COLUMNS = (
    "name",
    "full_name",
    "birth_date",
    "nationality",
    "positions",
    "position_group",
    "evaluation",
    "prediction_type",
)

#: Evaluation labels the system can produce.
EVALUATIONS: Tuple[str, ...] = (
    "Potentially Undervalued",
    "Fairly Valued",
    "Potentially Overvalued",
    "No recorded value",
)
POSITION_GROUPS: Tuple[str, ...] = ("GK", "DEF", "MID", "FWD")

_EMPTY_TOKENS = {"", "nan", "none", "null", "na", "n/a"}


class DataError(Exception):
    """Base class for problems with the prediction data."""


class DataFileNotFound(DataError):
    """The prediction table does not exist yet."""


class SchemaError(DataError):
    """The prediction table does not match the expected interface."""


def _is_blank(raw: Optional[str]) -> bool:
    return raw is None or raw.strip().lower() in _EMPTY_TOKENS


def _to_int(raw: Optional[str]) -> Optional[int]:
    if _is_blank(raw):
        return None
    value = float(raw)  # tolerate "1234.0" as well as "1234"
    return int(value)


def _to_float(raw: Optional[str]) -> Optional[float]:
    if _is_blank(raw):
        return None
    return float(raw)


def _to_text(raw: Optional[str]) -> Optional[str]:
    if _is_blank(raw):
        return None
    return raw.strip()


@dataclass(eq=False)
class PlayerDataset:
    """The prediction table held in memory, with a lookup index by player ID."""

    players: List[Dict[str, Any]] = field(default_factory=list)
    by_id: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    source_path: Optional[Path] = None

    def __len__(self) -> int:
        return len(self.players)

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        return iter(self.players)

    def get(self, player_id: int) -> Optional[Dict[str, Any]]:
        return self.by_id.get(int(player_id))


def _parse_row(row: Dict[str, str]) -> Dict[str, Any]:
    record: Dict[str, Any] = {}
    for column in INT_COLUMNS:
        record[column] = _to_int(row.get(column))
    for column in FLOAT_COLUMNS:
        record[column] = _to_float(row.get(column))
    for column in TEXT_COLUMNS:
        record[column] = _to_text(row.get(column))
    return record


def _validate(players: List[Dict[str, Any]], header: List[str]) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        raise SchemaError(
            "Prediction table is missing required column(s): "
            + ", ".join(missing)
            + ". The AI subsystem output does not match the interface contract in "
            "ai-core/INTERFACE_FOR_DASHBOARD.md."
        )

    problems: List[str] = []
    seen: set = set()

    for row_number, player in enumerate(players, start=2):  # row 1 is the header
        player_id = player["player_id"]
        if player_id is None:
            problems.append(f"row {row_number}: player_id is empty")
            continue
        if player_id in seen:
            problems.append(f"row {row_number}: duplicate player_id {player_id}")
        seen.add(player_id)

        predicted = player["predicted_value_eur"]
        if predicted is None or predicted <= 0:
            problems.append(f"row {row_number}: predicted_value_eur must be a positive number")

        label = player["evaluation"]
        if label not in EVALUATIONS:
            problems.append(f"row {row_number}: unknown evaluation label {label!r}")

        if len(problems) >= 10:  # enough to diagnose, not a wall of text
            problems.append("... further problems not listed")
            break

    if problems:
        raise SchemaError("Prediction table failed validation:\n  " + "\n  ".join(problems))


@lru_cache(maxsize=4)
def _load_cached(path_str: str, modified_time: float) -> PlayerDataset:
    """Read and validate the CSV. Cached per path and file modification time."""
    path = Path(path_str)
    players: List[Dict[str, Any]] = []

    # utf-8-sig removes a byte-order mark if the file was saved by Excel.
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        for row in reader:
            players.append(_parse_row(row))

    _validate(players, header)

    dataset = PlayerDataset(
        players=players,
        by_id={player["player_id"]: player for player in players},
        source_path=path,
    )
    return dataset


def load_dataset(path: Optional[Path] = None) -> PlayerDataset:
    """Load the prediction table, validating it against the interface contract.

    Raises:
        DataFileNotFound: the file is not there (the AI pipeline has not run yet).
        SchemaError: the file exists but does not match the expected interface.
    """
    target = Path(path) if path is not None else DEFAULT_PREDICTIONS_PATH
    if not target.exists():
        raise DataFileNotFound(
            f"Prediction table not found: {target}\n"
            "Run the AI pipeline first (see ai-core/README.md), or pass an explicit path."
        )
    return _load_cached(str(target), target.stat().st_mtime)


def clear_cache() -> None:
    """Drop the in-memory copy (used by tests)."""
    _load_cached.cache_clear()
