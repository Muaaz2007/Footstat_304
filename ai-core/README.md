# AI-Based Football Player Performance and Market Value Evaluation System

ICT304 group project. This folder holds the **AI subsystem prototype** (Subsystem 1):
dataset -> cleaning -> features -> two AI techniques -> comparison -> predicted market value
-> value difference -> evaluation category.

## Run it

```bash
pip install -r requirements.txt
cd ai
python preprocessing.py      # cleans the data -> data/processed/players_clean.csv
python train_compare.py      # trains + compares ridge regression vs random forest (~1 min)
python predict_evaluate.py   # predicts every player, sets thresholds, saves the model (~3 min)
cd .. && pytest -q           # smoke tests
```

Put `fifa_players.csv` in `data/raw/` first. All randomness uses seed 42.

## Files

| Path | What it does |
| --- | --- |
| `ai/preprocessing.py` | Loads data, adds `player_id`, repairs heights, builds features, drops leaky columns, saves `data/processed/players_clean.csv` |
| `ai/models.py` | Technique 1 (ridge linear regression) and Technique 2 (random forest) pipelines |
| `ai/train_compare.py` | 70/15/15 split, MAE / RMSE / R2 etc., 5-fold CV, error breakdown, feature importance |
| `ai/predict_evaluate.py` | Out-of-fold predictions, thresholds, categories, saved final model, `predict_player()` |
| `tests/test_prototype.py` | Smoke tests for loading, leakage, cleaning, classification and the output table |

## Cleaned dataset (`data/processed/players_clean.csv`)

All 17,954 players, 50 columns: `player_id`, display fields (name, full_name, birth_date,
nationality, positions, primary_position), the 40 model features, `value_euro`,
`has_value` (False for the 255 players with no recorded value) and `log_value` (the AI target).
Leaky, sparse and cosmetic columns are removed; heights are repaired.

## Outputs (`outputs/`)

| File | Contents |
| --- | --- |
| `model_comparison.csv` | Metrics per model and split |
| `error_breakdown.csv` | Test-set error by position group and value band |
| `rf_feature_importance.csv` | Random forest feature importance |
| `thresholds.json` | Category rule and the thresholds derived from model error |
| `player_predictions.csv` | One row per player: actual, predicted, difference, relative difference, evaluation |
| `market_value_model.joblib` | Final random forest (about 47 MB; git-ignored, regenerate with the script) |

## Evaluation categories

`r = log(predicted / actual)`, `k = 2 x robust SD of the model's out-of-fold log error` (about 0.095):

* `r > +k` (predicted at least ~1.10 x actual) -> **Potentially Undervalued**
* `r < -k` (predicted at most ~0.91 x actual) -> **Potentially Overvalued**
* otherwise -> **Fairly Valued**; no recorded value -> **No recorded value**

Labels describe the gap between the model's estimate and the dataset's recorded value,
not a real-world scouting judgement.

## Role in the larger system

This subsystem supports the whole project by producing predicted market value and the
comparison with recorded value. The dashboard is expected to use the prepared prediction
output described in `INTERFACE_FOR_DASHBOARD.md`, rather than retraining the model on
every use.
