"""Smoke tests for the AI prototype (run: pytest -q from the project root)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai"))
from preprocessing import FEATURES, LEAKY, SPARSE, clean, export_clean, load_raw, model_frame  # noqa: E402
from predict_evaluate import FAIR, NONE, OVER, UNDER, classify, predict_player  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "outputs"
RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "fifa_players.csv"

# The raw FIFA dataset is not stored in this repository. Anything that needs it is
# skipped with a reason, instead of failing with a confusing FileNotFoundError.
# See ai-core/data/raw/README.md to restore the file.
requires_raw = pytest.mark.skipif(
    not RAW.exists(),
    reason="needs ai-core/data/raw/fifa_players.csv (see ai-core/data/raw/README.md)",
)


@requires_raw
def test_dataset_loads():
    df = load_raw()
    assert df.shape == (17954, 52) and df.player_id.is_unique


def test_no_leaky_features():
    assert not set(LEAKY) & set(FEATURES)


@requires_raw
def test_height_repaired():
    h = clean(load_raw()).height_cm
    assert not h.isin([152.40, 154.94]).any()


@requires_raw
def test_model_frame_has_no_missing_target():
    _, X, y = model_frame(clean(load_raw()))
    assert len(X) == 17699 and not y.isna().any() and not X.isna().any().any()


@requires_raw
def test_clean_export(tmp_path):
    out = export_clean(clean(load_raw()), tmp_path / "players_clean.csv")
    saved = pd.read_csv(tmp_path / "players_clean.csv")
    assert len(saved) == 17954 and saved.player_id.is_unique
    assert saved.has_value.sum() == 17699
    assert not set(LEAKY + SPARSE + ["body_type"]) & set(saved.columns)
    assert not saved[FEATURES].isna().any().any()


def test_classify_rules():
    k = np.log(1.1)
    got = classify([200, 100, 50, 10], [100, 100, 100, np.nan], k)
    assert list(got) == [UNDER, FAIR, OVER, NONE]


@pytest.mark.skipif(not (OUT / "player_predictions.csv").exists(), reason="run ai/predict_evaluate.py first")
def test_predictions_table():
    t = pd.read_csv(OUT / "player_predictions.csv")
    assert len(t) == 17954 and t.predicted_value_eur.gt(0).all()
    assert {"player_id", "birth_date", "evaluation"} <= set(t.columns)
    assert predict_player(1)["name"] == "L. Messi"
    with pytest.raises(KeyError):
        predict_player(999999)
