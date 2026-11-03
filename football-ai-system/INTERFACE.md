# AI subsystem -> dashboard interface (v0.1, prototype)

Source: `outputs/player_predictions.csv` (one row per player, 17,954 rows),
or `predict_player(player_id)` in `ai/predict_evaluate.py` (returns the same row as a dict;
raises `KeyError` for an unknown ID).

Identify players by `player_id`, or by `name` + `birth_date`. Never by short name alone
(959 short names are shared by different players).

| Column | Type | Meaning |
| --- | --- | --- |
| player_id | int | Unique ID (row number of the raw CSV, 1-based) |
| name, full_name, birth_date, nationality, positions | text | Display fields from the dataset |
| age, overall_rating, potential | int | Display fields from the dataset |
| position_group | text | GK / DEF / MID / FWD (from the primary position) |
| actual_value_eur | float | Recorded value_euro; empty for 255 players |
| predicted_value_eur | float | Random forest estimate in euros (rounded to EUR 1,000) |
| value_difference_eur | float | predicted - actual; empty when actual is empty |
| relative_difference | float | (predicted - actual) / actual, e.g. -0.2826 = -28.26% |
| evaluation | text | Potentially Undervalued / Fairly Valued / Potentially Overvalued / No recorded value |
| prediction_type | text | "out-of-fold (5-fold CV)" or "final model" (players with no recorded value) |

Status: column names and meanings are frozen for integration. Values may change when the
model is tuned or the threshold is revised (the +/-0.095 log-ratio rule is PROPOSED, not final).
