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

This module needs the AI subsystem dependencies and a trained model:

```bash
pip install -r ai-core/requirements.txt
python ai-core/ai/predict_evaluate.py     # creates outputs/market_value_model.joblib
```

If the bundle or the dependencies are missing, the module raises an error that says what to
do, rather than silently returning a guess.

### Example

```python
from ai.live_inference import predict_player_value

result = predict_player_value(features, actual_value_eur=45_000_000)
# {'predicted_value_eur': 52000000.0, 'evaluation': 'Fairly Valued', ...}
```

`features` must contain every feature name the model was trained on. The list is stored
inside the bundle (`bundle["features"]`), so it always matches the saved model instead of
being duplicated by hand.

## Relationship to the interface document

The output fields follow `ai-core/INTERFACE_FOR_DASHBOARD.md`. The only addition is
`prediction_type = "live model"`, and `threshold_k_log` so a prediction can be explained
without opening the thresholds file.
