# Raw dataset

The AI pipeline reads its input from:

```
ai-core/data/raw/fifa_players.csv
```

The file **is included** in this repository (3.6 MB, 17,954 players, 51 columns). It is the
original source data, before the pipeline adds `player_id` and repairs anything.

## Provenance

| Property | Value |
| --- | --- |
| Source | Kaggle: `maso0dahmed/football-players-data` ("Football Players Data", from sofifa.com) |
| URL | https://www.kaggle.com/datasets/maso0dahmed/football-players-data |
| File in archive | `fifa_players.csv` |
| Retrieved | 4 November 2026 |
| Size | 3,664,954 bytes |
| Rows / columns | 17,954 / 51 (the pipeline adds `player_id`, giving 52) |

If the Kaggle licence is ever questioned, replace the committed file with this page's
download instructions and keep the rest of the repository unchanged: the raw file is only
needed to re-run training, and every output is committed.

## What it contains

| Property | Value |
| --- | --- |
| Players with a recorded value | 17,699 |
| Players with no recorded value | 255 |
| Corrupted heights present | yes — `152.40` and `154.94` cm, repaired by `preprocessing.py` |
| Columns `release_clause_euro`, `wage_euro`, `body_type` | present; dropped as leaky, leaky and cosmetic |
| National-team columns | present; dropped as 95% missing |

Column names the pipeline relies on are listed in `ai-core/ai/preprocessing.py`:
`SKILLS`, `NUMERIC_FEATURES`, `CATEGORICAL_FEATURES`, `LEAKY`, `SPARSE`, `COSMETIC`.

## Reproducing the pipeline

```bash
cd ai-core
pip install -r requirements.txt      # pinned versions, including scikit-learn 1.8.0

cd ai
python preprocessing.py      # -> data/processed/players_clean.csv
python train_compare.py      # ridge vs random forest
python predict_evaluate.py   # out-of-fold predictions, thresholds, model bundle
```

A full re-run on this file was verified to reproduce the committed results exactly (re-checked on 6 November 2026 with the tuned random forest, `max_features=1.0`):

| Output | Result |
| --- | --- |
| `thresholds.json` | byte-identical (`k_log = 0.08063261758267146`) |
| `player_predictions.csv` | byte-identical |
| `data/processed/players_clean.csv` | byte-identical |
| `model_comparison.csv`, `error_breakdown.csv`, `rf_feature_importance.csv` | differ only from the 10th significant digit down (floating-point noise between library builds) |
| Label counts | 14,750 / 1,452 / 1,497 / 255 — identical |
| Prototype tests | 7 passed |

Afterwards, run the suites:

```bash
python -m pytest ai-core/tests -q
python -m unittest discover -s backend/tests -t .
```
