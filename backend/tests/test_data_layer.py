"""Unit tests for the backend data layer (standard library unittest)."""
from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.loader import (  # noqa: E402
    EVALUATIONS,
    REQUIRED_COLUMNS,
    DataFileNotFound,
    SchemaError,
    clear_cache,
    load_dataset,
)
from backend.data.queries import (  # noqa: E402
    MAX_LIMIT,
    QueryError,
    lookup_by_name,
    metadata,
    query_players,
    summarize,
)

DATASET = load_dataset()


def write_csv(path: Path, header, rows) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return path


class TestLoading(unittest.TestCase):
    def setUp(self):
        clear_cache()

    def test_loads_every_player(self):
        self.assertEqual(len(DATASET), 17954)

    def test_players_indexed_by_id(self):
        self.assertEqual(len(DATASET.by_id), len(DATASET))
        self.assertEqual(DATASET.get(1)["name"], "L. Messi")
        self.assertIsNone(DATASET.get(999999))

    def test_values_are_typed(self):
        player = DATASET.get(1)
        self.assertIsInstance(player["player_id"], int)
        self.assertIsInstance(player["predicted_value_eur"], float)
        self.assertGreater(player["predicted_value_eur"], 0)

    def test_missing_file_is_reported(self):
        with self.assertRaises(DataFileNotFound):
            load_dataset(Path("does/not/exist.csv"))

    def test_missing_column_is_rejected(self):
        header = [column for column in REQUIRED_COLUMNS if column != "evaluation"]
        with tempfile.TemporaryDirectory() as folder:
            path = write_csv(
                Path(folder) / "broken.csv",
                header,
                [[1] * len(header)],
            )
            with self.assertRaises(SchemaError) as caught:
                load_dataset(path)
            self.assertIn("evaluation", str(caught.exception))

    def test_bad_prediction_value_is_rejected(self):
        row = {column: "1" for column in REQUIRED_COLUMNS}
        row["evaluation"] = EVALUATIONS[0]
        row["predicted_value_eur"] = "-5"
        with tempfile.TemporaryDirectory() as folder:
            path = write_csv(
                Path(folder) / "bad_value.csv",
                list(REQUIRED_COLUMNS),
                [[row[column] for column in REQUIRED_COLUMNS]],
            )
            with self.assertRaises(SchemaError) as caught:
                load_dataset(path)
            self.assertIn("predicted_value_eur", str(caught.exception))


class TestQueries(unittest.TestCase):
    def test_search_matches_name(self):
        # Search is a substring match over the display fields, so "messi" also
        # matches players called "Messias". Every result must still contain the
        # term somewhere in its name or full name.
        result = query_players(DATASET, search="messi", limit=MAX_LIMIT)
        self.assertGreaterEqual(result["total"], 1)
        self.assertEqual(result["results"][0]["player_id"], 1)
        for player in result["results"]:
            text = f"{player['name']} {player['full_name']}".lower()
            self.assertIn("messi", text)

    def test_search_requires_all_words(self):
        result = query_players(DATASET, search="messi argentina", limit=MAX_LIMIT)
        self.assertGreaterEqual(result["total"], 1)
        self.assertEqual(result["results"][0]["player_id"], 1)

    def test_filter_by_position_group(self):
        result = query_players(DATASET, position_group="GK", limit=MAX_LIMIT)
        self.assertGreater(result["total"], 0)
        self.assertTrue(all(player["position_group"] == "GK" for player in result["results"]))

    def test_filter_by_evaluation(self):
        result = query_players(DATASET, evaluation="Fairly Valued", limit=MAX_LIMIT)
        self.assertGreater(result["total"], 0)
        self.assertTrue(
            all(player["evaluation"] == "Fairly Valued" for player in result["results"])
        )

    def test_sort_descending(self):
        result = query_players(
            DATASET, sort="predicted_value_eur", order="desc", limit=10
        )
        values = [player["predicted_value_eur"] for player in result["results"]]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_sort_puts_missing_values_last(self):
        total = query_players(DATASET, limit=1)["total"]
        tail = query_players(
            DATASET, sort="actual_value_eur", order="asc", limit=5, offset=total - 5
        )["results"]
        self.assertTrue(all(player["actual_value_eur"] is None for player in tail))

    def test_pagination(self):
        page_one = query_players(DATASET, limit=5, offset=0)
        page_two = query_players(DATASET, limit=5, offset=5)
        self.assertEqual(page_one["count"], 5)
        self.assertEqual(page_one["total"], page_two["total"])
        self.assertNotEqual(
            [player["player_id"] for player in page_one["results"]],
            [player["player_id"] for player in page_two["results"]],
        )

    def test_invalid_arguments_raise(self):
        with self.assertRaises(QueryError):
            query_players(DATASET, sort="wage")
        with self.assertRaises(QueryError):
            query_players(DATASET, order="sideways")
        with self.assertRaises(QueryError):
            query_players(DATASET, position_group="COACH")
        with self.assertRaises(QueryError):
            query_players(DATASET, evaluation="Bargain")
        with self.assertRaises(QueryError):
            query_players(DATASET, limit=MAX_LIMIT + 1)
        with self.assertRaises(QueryError):
            query_players(DATASET, offset=-1)

    def test_lookup_by_name_is_ambiguous_by_design(self):
        exact = lookup_by_name(DATASET, "L. Messi")
        self.assertEqual([player["player_id"] for player in exact], [1])
        narrowed = lookup_by_name(DATASET, "L. Messi", "6/24/1987")
        self.assertEqual(len(narrowed), 1)
        self.assertEqual(narrowed[0]["player_id"], 1)
        self.assertEqual(lookup_by_name(DATASET, "L. Messi", "1/1/1990"), [])

    def test_summary_is_consistent(self):
        summary = summarize(DATASET)
        self.assertEqual(summary["total_players"], len(DATASET))
        self.assertEqual(
            summary["players_with_recorded_value"] + summary["players_without_recorded_value"],
            summary["total_players"],
        )
        self.assertEqual(sum(summary["evaluation_counts"].values()), summary["total_players"])
        self.assertEqual(sum(summary["position_group_counts"].values()), summary["total_players"])
        self.assertEqual(summary["evaluation_counts"]["No recorded value"], 255)
        self.assertEqual(len(summary["most_undervalued"]), 5)

    def test_metadata_lists_contract_values(self):
        meta = metadata(DATASET)
        self.assertEqual(meta["player_count"], len(DATASET))
        self.assertIn("predicted_value_eur", meta["sortable_columns"])
        self.assertEqual(meta["max_limit"], MAX_LIMIT)


if __name__ == "__main__":
    unittest.main()
