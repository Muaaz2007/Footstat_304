"""Live prediction path for a single player record.

The architecture document keeps the trained model available "for possible live
prediction or future functionality". This module is that path: it loads the
model bundle saved by ``ai-core/ai/predict_evaluate.py`` and scores one player
whose attributes are supplied by the caller, instead of reading a row from the
prepared prediction table.

When to use it
--------------
* The dashboard reads ``player_predictions.csv`` for normal use. That is the
  primary, fast path and it does not need scikit-learn installed.
* This module is for cases where the player is not in that table, for example a
  newly added player, or for explaining a single prediction.

It requires the AI subsystem's dependencies (pandas, scikit-learn, joblib) and a
trained bundle. If either is missing it raises a clear error instead of
pretending to work.

Example
-------
>>> from ai.live_inference import predict_player_value
>>> predict_player_value({
...     "age": 27, "height_cm": 180, "weight_kgs": 75,
...     "overall_rating": 84, "potential": 86, "potential_gap": 2,
...     "international_reputation(1-5)": 2, "weak_foot(1-5)": 3,
...     "skill_moves(1-5)": 4, "position_group": "FWD",
...     "preferred_foot": "Right",
...     # ... every remaining skill feature
... })
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]

# The prototype has saved the bundle in two places: inside outputs/ and directly
# in ai-core/. Check both, so a moved file is found instead of silently breaking
# live prediction.
BUNDLE_CANDIDATES = (
    ROOT / "ai-core" / "outputs" / "market_value_model.joblib",
    ROOT / "ai-core" / "market_value_model.joblib",
)
BUNDLE_PATH = BUNDLE_CANDIDATES[0]

UNDER = "Potentially Undervalued"
FAIR = "Fairly Valued"
OVER = "Potentially Overvalued"
NONE = "No recorded value"


def _require_dependencies():
    """Import the AI dependencies, or explain what is missing."""
    try:
        import joblib  # noqa: F401
        import pandas as pd  # noqa: F401
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError(
            "Live prediction needs the AI subsystem dependencies. "
            "Install them with: pip install -r ai-core/requirements.txt"
        ) from exc


def load_bundle(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load the saved model bundle: model, feature list and thresholds."""
    _require_dependencies()
    import joblib

    if path is not None:
        target = Path(path)
    else:
        target = next((p for p in BUNDLE_CANDIDATES if p.exists()), None)
        if target is None:
            looked = "\n  ".join(str(p) for p in BUNDLE_CANDIDATES)
            raise FileNotFoundError(
                "Model bundle not found. Looked in:\n  " + looked + "\n"
                "Run ai/predict_evaluate.py inside ai-core/ to create it."
            )
    return joblib.load(target)


def _coerce(value: Any) -> Any:
    """Turn numeric strings into numbers, e.g. values read straight from a CSV.

    Categorical features (position group, preferred foot) are left as text, since
    the model was trained with those as categories.
    """
    if isinstance(value, str):
        text = value.strip()
        try:
            return float(text)
        except ValueError:
            return text
    return value


def classify(predicted: float, actual: Optional[float], k: float) -> str:
    """Apply the same threshold rule the prototype uses, for one player."""
    if actual is None or actual <= 0:
        return NONE
    ratio = math.log(predicted / actual)
    if ratio > k:
        return UNDER
    if ratio < -k:
        return OVER
    return FAIR


def predict_player_value(
    player: Dict[str, Any],
    *,
    actual_value_eur: Optional[float] = None,
    bundle: Optional[Dict[str, Any]] = None,
    bundle_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Estimate one player's market value and, if a value is given, evaluate it.

    Args:
        player: mapping of feature name to value. Every feature in the model
            bundle must be present.
        actual_value_eur: recorded value to compare against, if known.
        bundle: an already loaded bundle (avoids re-reading the model).
        bundle_path: alternative location for the bundle file.

    Returns:
        A dict in the same shape as a row of ``player_predictions.csv``, so the
        dashboard can use live and precomputed results the same way.
    """
    _require_dependencies()
    import pandas as pd

    bundle = bundle if bundle is not None else load_bundle(bundle_path)
    features = list(bundle["features"])

    missing = [name for name in features if name not in player]
    if missing:
        raise ValueError(
            "Player record is missing required feature(s): " + ", ".join(missing)
        )

    frame = pd.DataFrame([{name: _coerce(player[name]) for name in features}])
    log_prediction = float(bundle["model"].predict(frame)[0])
    predicted = math.exp(log_prediction)

    k = float(bundle["thresholds"]["k_log"])
    actual = None if actual_value_eur is None else float(actual_value_eur)

    # Report the value rounded to thousands, as the prediction table does, and
    # derive the difference from that same rounded figure. Otherwise the numbers
    # shown to the user would not add up.
    reported = float(round(predicted, -3))
    difference = None if actual is None else reported - actual
    relative = None if not actual else (reported - actual) / actual

    return {
        "actual_value_eur": actual,
        "predicted_value_eur": reported,
        "value_difference_eur": None if difference is None else round(difference, 2),
        "relative_difference": None if relative is None else round(relative, 4),
        "evaluation": classify(predicted, actual, k),
        "prediction_type": "live model",
        "threshold_k_log": k,
    }
