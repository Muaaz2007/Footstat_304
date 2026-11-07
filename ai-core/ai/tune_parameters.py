"""Hyper-parameter optimisation for the two AI techniques (one variable at a time).

Run from ai-core/ai:  python tune_parameters.py
Uses the same 70/15/15 split (seed 42) as train_compare.py. Every setting is scored on
the validation set only; the test set is never touched here. Results are written to
ai-core/outputs/tuning_results.csv.
"""
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
from sklearn.base import clone

from models import SEED, linear_regression, random_forest
from preprocessing import clean, load_raw, model_frame
from train_compare import split

OUT = Path(__file__).resolve().parents[1] / "outputs"

# Starting point: the prototype's settings. Each sweep changes one of them.
BASE = {"n_estimators": 300, "max_features": 0.5, "min_samples_leaf": 2}
# Final check: the best single change, alone and combined with the other best values.
COMBINED = [(1.0, 300, 2), (1.0, 300, 1), (1.0, 500, 2), (1.0, 500, 1)]
SWEEPS = {
    "n_estimators": [50, 100, 300, 500],
    "max_features": [0.2, 0.33, 0.5, 0.7, 1.0],
    "min_samples_leaf": [1, 2, 5, 10],
}


def scores(y_true_log, y_pred_log):
    t, p = np.exp(y_true_log), np.exp(y_pred_log)
    ape = np.abs(p - t) / t
    return {"MedianAPE_pct": float(np.median(ape) * 100), "Within25pct_pct": float(np.mean(ape <= 0.25) * 100),
            "MAE_eur": float(np.mean(np.abs(p - t)))}


def main():
    _, X, y = model_frame(clean(load_raw()))
    X_tr, X_va, X_te, y_tr, y_va, y_te = split(X, y)
    rows = []

    # Random forest: change one parameter at a time, the others held at BASE.
    for param, values in SWEEPS.items():
        for v in values:
            m = random_forest()
            m.set_params(**{f"model__{k}": val for k, val in {**BASE, param: v}.items()})
            t0 = time.time(); m.fit(X_tr, y_tr); secs = time.time() - t0
            rows.append({"model": "Random forest", "parameter": param, "value": v,
                         "fit_seconds": round(secs, 1), **scores(y_va, m.predict(X_va))})
            print(rows[-1])

    for mf, n, leaf in COMBINED:
        m = random_forest()
        m.set_params(model__max_features=mf, model__n_estimators=n, model__min_samples_leaf=leaf)
        m.fit(X_tr, y_tr)
        rows.append({"model": "Random forest", "parameter": "combined",
                     "value": f"max_features={mf}, n_estimators={n}, min_samples_leaf={leaf}",
                     **scores(y_va, m.predict(X_va))})
        print(rows[-1])

    # Ridge: the alpha path (each alpha fitted on its own).
    for a in [0.001, 0.01, 0.1, 1, 10, 100, 1000]:
        m = linear_regression()
        m.set_params(model__alphas=[a])
        m.fit(X_tr, y_tr)
        rows.append({"model": "Ridge", "parameter": "alpha", "value": a, **scores(y_va, m.predict(X_va))})
        print(rows[-1])

    pd.DataFrame(rows).to_csv(OUT / "tuning_results.csv", index=False)

    # Paired comparison of the two final techniques on the test set (same players).
    rf, rg = random_forest().fit(X_tr, y_tr), linear_regression().fit(X_tr, y_tr)
    e_rf = np.abs(rf.predict(X_te) - y_te.values)
    e_rg = np.abs(rg.predict(X_te) - y_te.values)
    stat, p = wilcoxon(e_rf, e_rg)
    print(f"test players {len(y_te)}; RF closer on {np.mean(e_rf < e_rg) * 100:.1f}%; "
          f"Wilcoxon signed-rank p = {p:.3g}")


if __name__ == "__main__":
    main()
