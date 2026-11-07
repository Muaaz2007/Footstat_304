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
python tune_parameters.py    # optional: parameter optimisation, one at a time (~11 min)
cd .. && pytest -q           # smoke tests
```

`data/raw/fifa_players.csv` is included (17,954 rows, from Kaggle). All randomness uses seed 42,
and a full re-run reproduces the committed outputs — see `data/raw/README.md` for the
verification table.

## Files

| Path | What it does |
| --- | --- |
| `ai/preprocessing.py` | Loads data, adds `player_id`, repairs heights, builds features, drops leaky columns, saves `data/processed/players_clean.csv` |
| `ai/models.py` | Technique 1 (ridge linear regression) and Technique 2 (random forest) pipelines |
| `ai/train_compare.py` | 70/15/15 split, MAE / RMSE / R2 etc., 5-fold CV, error breakdown, feature importance |
| `ai/tune_parameters.py` | Parameter optimisation on the validation set (one at a time, then combined) and the paired Wilcoxon test; writes `outputs/tuning_results.csv` |
| `ai/predict_evaluate.py` | Out-of-fold predictions, thresholds, categories, saved final model, `predict_player()` |
| `tests/test_prototype.py` | Smoke tests for loading, leakage, cleaning, classification and the output table |
| `ai/fetch_current_values.py` | Optional: fetches current market values from Transfermarkt through an Apify Actor (paid, needs `APIFY_API_TOKEN`) |
| `ai/build_reference_values.py` | Turns that raw result into `data/reference/current_values.csv` |
| `ai/compare_then_now.py` | Compares the dataset's snapshot values with current values: drift, and whether the labels change |

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
| `market_value_model.joblib` | Final random forest (about 39 MB; git-ignored, regenerate with the script) |

## Evaluation categories

`r = log(predicted / actual)`, `k = 2 x robust SD of the model's out-of-fold log error` (about 0.081):

* `r > +k` (predicted at least ~1.08 x actual) -> **Potentially Undervalued**
* `r < -k` (predicted at most ~0.92 x actual) -> **Potentially Overvalued**
* otherwise -> **Fairly Valued**; no recorded value -> **No recorded value**

Labels describe the gap between the model's estimate and the dataset's recorded value,
not a real-world scouting judgement.

## The math and the buffer, in numbers

`BUFFER_MATH_AND_VALUE_CHECK.md` explains where `k` comes from, how wide the buffer is in
euros at different value levels, what happens if it is narrowed or widened (with counts),
and how to check how much the dataset's values have aged by comparing them with current
Transfermarkt values.

In short: `k = 2 x robust sigma` of the model's out-of-fold log error = 0.0806, so the
model must disagree with the recorded value by about 8% before a label is applied, and the
buffer is about +/- 0.8M on a 10M player and +/- 8M on a 100M player.

## Role in the larger system

This subsystem supports the whole project by producing predicted market value and the
comparison with recorded value. The dashboard is expected to use the prepared prediction
output described in `INTERFACE_FOR_DASHBOARD.md`, rather than retraining the model on
every use.
