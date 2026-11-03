# AI subsystem to dashboard interface

## Purpose

This document describes the handoff between the AI subsystem and the dashboard/application side of the system.

The architecture separates the work into two related processes:

- **Offline AI development**: dataset -> data processing -> feature selection -> model training -> model comparison -> selected model -> prediction/evaluation generation -> `player_predictions.csv`
- **Runtime dashboard use**: user -> dashboard -> player selection -> `player_predictions.csv` -> player results -> user

The point of this split is that model training is not needed every time a user opens the dashboard. The AI subsystem prepares the results once, and the dashboard retrieves them.

## Main output file

The AI subsystem produces `player_predictions.csv` as its main interface to the dashboard. This file contains one row per player and is the primary source the dashboard should use for player-level results during normal use.

The trained model file `market_value_model.joblib` is also available, but it is not required for the current dashboard workflow. It is kept for possible live prediction or future functionality.

## How a player is identified

Players should be identified by `player_id`, or by a combination of `name` and `birth_date`.

A player should not be identified by short name alone, because some short names are shared by different players. Using `player_id` is the most reliable method.

## Fields the dashboard can use

The AI subsystem provides the following kinds of information for each player:

- **Identity and display fields**: `player_id`, `name`, `full_name`, `birth_date`, `nationality`, `positions`
- **Basic player attributes**: `age`, `overall_rating`, `potential`, `position_group`
- **Recorded market value**: `actual_value_eur`, where available
- **Predicted market value**: `predicted_value_eur`
- **Value comparison**: `value_difference_eur` and `relative_difference`
- **Evaluation result**: `evaluation`
- **Prediction type information**: `prediction_type`

The exact column names and meanings should be treated as the interface contract. The dashboard can rely on these meanings, but the actual values may change if the model or thresholds are revised later.

## Column meanings

- `player_id`
  Unique identifier for the player.

- `name`, `full_name`, `birth_date`, `nationality`, `positions`
  Display fields taken from the dataset.

- `age`, `overall_rating`, `potential`
  Display fields taken from the dataset.

- `position_group`
  Broad position category derived from the player's primary position, for example GK, DEF, MID, FWD.

- `actual_value_eur`
  The recorded market value from the dataset. This may be empty for some players.

- `predicted_value_eur`
  The AI model's estimated market value.

- `value_difference_eur`
  The difference between the predicted value and the recorded value. This is empty when the recorded value is empty.

- `relative_difference`
  The relative difference between predicted and recorded value.

- `evaluation`
  The evaluation category produced by the system, such as Potentially Undervalued, Fairly Valued, Potentially Overvalued, or No recorded value.

- `prediction_type`
  Indicates whether the prediction comes from out-of-fold prediction or from the final model, depending on the player.

## How the dashboard should use this interface

At runtime, the dashboard should:

1. Let the user select a player.
2. Look up that player in `player_predictions.csv`.
3. Show the player's display information.
4. Show the recorded value where available.
5. Show the predicted value.
6. Show the difference and relative difference.
7. Show the evaluation category.

The dashboard does not need to run the AI model itself during normal use. It only needs to read the prepared prediction file.

## Prediction type

For players with a recorded value, the prototype uses out-of-fold predictions so that a player is not evaluated by a model trained on that same player's data. For some players, the prediction may instead come from the final model. The `prediction_type` field records which case applies.

## Status of the interface

The column names and meanings described here are intended to be stable for integration. The values may change later if the model is tuned or the threshold rule is revised, but the interface itself should remain understandable in the same way.

## Important limitation

The evaluation is based on the relationship between the model's predicted value and the dataset's recorded value. It is an AI-based indication, not a definitive statement of a player's true market value.

The market value data limitation and the tradeoff/strategy used to handle it are described separately in `MARKET_VALUE_LIMITATION_AND_STRATEGY.md`.
