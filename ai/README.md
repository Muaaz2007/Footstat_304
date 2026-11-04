# AI runtime module

This folder holds the **runtime** part of the AI work: predicting a single player's market
value on demand. The offline pipeline that trains and compares models lives in
`ai-core/`.

## Why the split

The architecture document separates two processes:

- **Offline AI development** (`ai-core/`): cleaning, feature preparation, model training,
  model comparison, prediction of every player, and the evaluation table.
- **Runtime use** (this folder and `backend/`): answering questions about a player while
  the system is running.

Normal dashboard use reads the prepared table in `ai-core/outputs/player_predictions.csv`.
That path is fast and needs no machine-learning libraries at all. The module here exists
for the case where a player is not in that table, for example a newly added player, or when
a single prediction needs to be explained.

## `live_inference.py`

| Function | Purpose |
| --- | --- |
| `load_bundle(path=None)` | Loads the saved bundle (model, feature list, thresholds) |
| `classify(predicted, actual, k)` | Applies the same threshold rule used by the prototype |
| `predict_player_value(player, actual_value_eur=None, ...)` | Predicts one player's value and, when a recorded value is supplied, its evaluation |

`predict_player_value` returns a dict in the same shape as a row of
`player_predictions.csv`, so the dashboard can treat live and precomputed results the same
way.

### Requirements

This module needs the AI subsystem dependencies and a trained model bundle:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r ai-core/requirements.txt   # Windows
# .venv/bin/python -m pip install -r ai-core/requirements.txt     # macOS/Linux
```

The bundle is looked for in `ai-core/outputs/market_value_model.joblib` and then in
`ai-core/market_value_model.joblib`, so it works whichever place it was saved to. If it is
missing, the module says so and names the paths it checked instead of silently returning a
guess.

To recreate the bundle, run `python ai/predict_evaluate.py` inside `ai-core/`, which needs
`ai-core/data/raw/fifa_players.csv`.

A note on versions: the saved bundle was trained with scikit-learn 1.8.0. Loading it with a
different version raises an `InconsistentVersionWarning`. Predictions still come out
sensible, but pin the version if the results must be reproducible exactly.

### Example

```python
from ai.live_inference import predict_player_value

result = predict_player_value(features, actual_value_eur=45_000_000)
# {'predicted_value_eur': 52000000.0, 'evaluation': 'Fairly Valued', ...}
```

`features` must contain every feature name the model was trained on. The list is stored
inside the bundle (`bundle["features"]`), so it always matches the saved model instead of
being duplicated by hand. Values may be numbers or numeric strings, so a record read from a
CSV or a JSON request works without extra conversion.

### Tests

The module has its own tests, which skip themselves when the dependencies are absent:

```bash
.venv/Scripts/python -m unittest discover -s ai/tests -t . -v
```

They check the bundle contents, the threshold rule at its boundaries, the shape of the
result, a player with no recorded value, a missing feature, and a missing bundle.

## Relationship to the interface document

The output fields follow `ai-core/INTERFACE_FOR_DASHBOARD.md`. The only addition is
`prediction_type = "live model"`, and `threshold_k_log` so a prediction can be explained
without opening the thresholds file.
