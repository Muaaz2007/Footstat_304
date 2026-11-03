"""Prototype step 2: predict every player's market value and classify it.

* Players with a recorded value get an OUT-OF-FOLD prediction (5-fold): each
  player is predicted by a forest that never saw them, so the comparison with
  the recorded value is fair.
* A final forest trained on all 17,699 valued players is saved for new or
  unvalued players (the 255 with no recorded value).
* Category thresholds come from the model's own out-of-sample error.
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold, cross_val_predict

from models import SEED, random_forest
from preprocessing import FEATURES, TARGET, clean, load_raw, model_frame

OUT = Path(__file__).resolve().parents[1] / "outputs"
OUT.mkdir(exist_ok=True)
K_SIGMA = 2.0  # flag when the gap exceeds 2 robust SDs of the model's own error

UNDER, FAIR, OVER, NONE = "Potentially Undervalued", "Fairly Valued", "Potentially Overvalued", "No recorded value"


def robust_sigma(x) -> float:
    x = np.asarray(x)
    return float(1.4826 * np.median(np.abs(x - np.median(x))))


def classify(predicted, actual, k):
    """Category from the log ratio log(predicted / actual) and threshold k."""
    predicted, actual = np.asarray(predicted, float), np.asarray(actual, float)
    out = np.full(len(predicted), NONE, dtype=object)
    has = ~np.isnan(actual)
    r = np.log(predicted[has] / actual[has])
    out[has] = np.where(r > k, UNDER, np.where(r < -k, OVER, FAIR))
    return out


def main():
    df = clean(load_raw())
    valued, X, y = model_frame(df)

    # 1. Out-of-fold predictions for every valued player.
    oof = cross_val_predict(random_forest(), X, y, cv=KFold(5, shuffle=True, random_state=SEED), n_jobs=1)
    sigma = robust_sigma(oof - y)
    k = K_SIGMA * sigma
    thresholds = {
        "rule": "log(predicted/actual) > +k -> Undervalued; < -k -> Overvalued; else Fairly Valued",
        "k_sigma": K_SIGMA, "robust_sigma_log": sigma, "k_log": k,
        "undervalued_if_predicted_at_least_x_actual": float(np.exp(k)),
        "overvalued_if_predicted_at_most_x_actual": float(np.exp(-k)),
    }
    json.dump(thresholds, open(OUT / "thresholds.json", "w"), indent=2)

    # 2. Final model on all valued players, saved for the dashboard / new players.
    final = random_forest().fit(X, y)
    joblib.dump({"model": final, "features": FEATURES, "thresholds": thresholds},
                OUT / "market_value_model.joblib", compress=3)

    # 3. Assemble the evaluation table the dashboard reads.
    pred = pd.Series(np.nan, index=df.index)
    pred[df[TARGET].notna()] = np.exp(oof)
    no_val = df[TARGET].isna()
    pred[no_val] = np.exp(final.predict(df.loc[no_val, FEATURES]))

    res = df[["player_id", "name", "full_name", "birth_date", "age", "nationality", "positions", "position_group",
              "overall_rating", "potential", TARGET]].rename(columns={TARGET: "actual_value_eur"})
    res["predicted_value_eur"] = pred.round(-3)
    res["value_difference_eur"] = res.predicted_value_eur - res.actual_value_eur
    res["relative_difference"] = (res.value_difference_eur / res.actual_value_eur).round(4)
    res["evaluation"] = classify(pred.values, res.actual_value_eur.values, k)
    res["prediction_type"] = np.where(no_val, "final model", "out-of-fold (5-fold CV)")
    res.to_csv(OUT / "player_predictions.csv", index=False)

    print(json.dumps(thresholds, indent=2))
    print(res.evaluation.value_counts().to_string())


def predict_player(player_id: int, model_path=OUT / "market_value_model.joblib") -> dict:
    """Integration hook for the dashboard: one player's evaluation by ID.

    Uses the precomputed out-of-fold table so a player is never scored by a
    model that trained on them.
    """
    table = pd.read_csv(OUT / "player_predictions.csv")
    row = table[table.player_id == player_id]
    if row.empty:
        raise KeyError(f"No player with player_id={player_id}")
    return row.iloc[0].to_dict()


if __name__ == "__main__":
    main()
