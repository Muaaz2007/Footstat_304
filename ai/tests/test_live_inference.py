"""Tests for the live single-player prediction path.

These need the AI subsystem dependencies and the trained model bundle. When those
are missing the tests are skipped with a message, so the backend suite can still
be run on a machine without scikit-learn.

Run from the project root:

    .venv/Scripts/python -m unittest discover -s ai/tests -t . -v      (Windows)
    .venv/bin/python -m unittest discover -s ai/tests -t . -v          (macOS/Linux)
"""
import csv
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "ai-core" / "data" / "processed" / "players_clean.csv"

try:
    import joblib  # noqa: F401
    import pandas  # noqa: F401

    HAVE_DEPENDENCIES = True
except ImportError:
    HAVE_DEPENDENCIES = False

SKIP_REASON = "needs pandas and joblib: pip install -r ai-core/requirements.txt"


@unittest.skipUnless(HAVE_DEPENDENCIES, SKIP_REASON)
class TestLiveInference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ai import live_inference

        cls.mod = live_inference
        cls.bundle = live_inference.load_bundle()
        with open(CLEAN, newline="", encoding="utf-8") as handle:
            cls.players = {row["player_id"]: row for row in csv.DictReader(handle)}

    def features(self, player_id):
        """Feature values for one player, taken straight from the cleaned CSV.

        Passed as strings on purpose: that is what a caller reading a CSV or a
        JSON request would have.
        """
        row = self.players[str(player_id)]
        return {name: row[name] for name in self.bundle["features"]}

    def test_bundle_matches_the_interface(self):
        self.assertEqual(sorted(self.bundle), ["features", "model", "thresholds"])
        self.assertEqual(len(self.bundle["features"]), 40)
        self.assertIn("position_group", self.bundle["features"])
        self.assertIn("k_log", self.bundle["thresholds"])

    def test_classify_uses_the_threshold_rule(self):
        k = 0.1
        self.assertEqual(self.mod.classify(110.0, 100.0, k), self.mod.FAIR)
        self.assertEqual(self.mod.classify(120.0, 100.0, k), self.mod.UNDER)
        self.assertEqual(self.mod.classify(80.0, 100.0, k), self.mod.OVER)
        self.assertEqual(self.mod.classify(50.0, None, k), self.mod.NONE)

    def test_prediction_returns_the_table_shape(self):
        result = self.mod.predict_player_value(
            self.features(50), actual_value_eur=34_000_000, bundle=self.bundle
        )
        for field in (
            "actual_value_eur",
            "predicted_value_eur",
            "value_difference_eur",
            "relative_difference",
            "evaluation",
            "prediction_type",
        ):
            self.assertIn(field, result)
        self.assertEqual(result["prediction_type"], "live model")
        self.assertGreater(result["predicted_value_eur"], 0)
        self.assertEqual(result["predicted_value_eur"] % 1000, 0)
        self.assertAlmostEqual(
            result["value_difference_eur"],
            result["predicted_value_eur"] - 34_000_000,
            places=2,
        )

    def test_player_without_a_recorded_value(self):
        player_id = next(
            key for key, row in self.players.items() if not row["value_euro"]
        )
        result = self.mod.predict_player_value(self.features(player_id), bundle=self.bundle)
        self.assertIsNone(result["actual_value_eur"])
        self.assertIsNone(result["relative_difference"])
        self.assertEqual(result["evaluation"], self.mod.NONE)
        self.assertGreater(result["predicted_value_eur"], 0)

    def test_missing_feature_is_reported(self):
        features = self.features(50)
        features.pop("crossing")
        with self.assertRaises(ValueError) as caught:
            self.mod.predict_player_value(features, bundle=self.bundle)
        self.assertIn("crossing", str(caught.exception))

    def test_missing_bundle_is_reported(self):
        with self.assertRaises(FileNotFoundError):
            self.mod.load_bundle(ROOT / "ai-core" / "does_not_exist.joblib")


if __name__ == "__main__":
    unittest.main()
