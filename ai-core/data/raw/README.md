# Raw dataset (not stored in this repository)

The AI pipeline reads its input from:

```
ai-core/data/raw/fifa_players.csv
```

That file is **not** in the repository, because it is a third-party dataset and is large.
Everything downstream of it (the cleaned dataset, the prediction table, the model bundle) is
already committed, so the rest of the system runs without it. Only the training and
preprocessing steps need the original file.

## Why this matters

Without this file the pipeline cannot be re-run or re-trained, so these four prototype tests
are skipped rather than run:

```
test_dataset_loads
test_height_repaired
test_model_frame_has_no_missing_target
test_clean_export
```

They report `skipped` with the reason, instead of failing with `FileNotFoundError`.

## What the file must contain

| Property | Value |
| --- | --- |
| Rows | 17,954 players, no ID column (the pipeline adds `player_id`) |
| Columns | 52, as delivered by the source |
| Overlap check | `preprocessing.py` needs `positions`, `height_cm`, `weight_kgs`, `age`, `overall_rating`, `potential`, `preferred_foot`, `value_euro`, the 29 skill columns, plus `release_clause_euro`, `wage_euro`, `body_type` and the national-team columns that get dropped |

The column names are listed in `ai-core/ai/preprocessing.py`: `SKILLS`, `NUMERIC_FEATURES`,
`CATEGORICAL_FEATURES`, `LEAKY`, `SPARSE`, `COSMETIC`.

## How to restore it

1. Get the dataset from the source the group used (FIFA player dataset, 17,954 rows).
2. Save it as `ai-core/data/raw/fifa_players.csv` with the same column names.
3. Check it loads:

```bash
cd ai-core
python ai/preprocessing.py     # prints "17954 players loaded, 17699 with a recorded value"
```

4. Then the tests run in full:

```bash
python -m pytest ai-core/tests -q
```

## For the report

State the source, the version and the date you downloaded it, and whether the licence allows
redistribution. Do not commit the file if the licence does not allow it — documenting how to
obtain it is enough, and that is what this page does.
