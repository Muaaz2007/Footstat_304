"""Train both techniques, evaluate on validation and test sets, and compare.

Split: 70% train / 15% validation / 15% test, fixed seed.
Metrics are reported in euros (after undoing the log) and on the log scale.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_score, train_test_split

from models import CANDIDATES, SEED
from preprocessing import clean, load_raw, model_frame

OUT = Path(__file__).resolve().parents[1] / "outputs"
OUT.mkdir(exist_ok=True)


def metrics(y_log_true, y_log_pred) -> dict:
    t, p = np.exp(np.asarray(y_log_true)), np.exp(np.asarray(y_log_pred))
    return {
        "MAE_eur": mean_absolute_error(t, p),
        "RMSE_eur": float(np.sqrt(mean_squared_error(t, p))),
        "R2_eur": r2_score(t, p),
        "R2_log": r2_score(np.log(t), np.log(p)),
        "MedianAPE_pct": float(np.median(np.abs(p - t) / t) * 100),
        "Within25pct_pct": float(np.mean(np.abs(p - t) / t <= 0.25) * 100),
    }


def split(X, y):
    X_tr, X_tmp, y_tr, y_tmp = train_test_split(X, y, test_size=0.30, random_state=SEED)
    X_va, X_te, y_va, y_te = train_test_split(X_tmp, y_tmp, test_size=0.50, random_state=SEED)
    return X_tr, X_va, X_te, y_tr, y_va, y_te


def main():
    df = clean(load_raw())
    train_df, X, y = model_frame(df)
    X_tr, X_va, X_te, y_tr, y_va, y_te = split(X, y)
    print(f"train {len(X_tr)}  validation {len(X_va)}  test {len(X_te)}")

    rows, fitted = [], {}
    med = np.full(len(y_te), np.median(y_tr))  # naive reference: everyone gets the median
    rows.append({"model": "Baseline (median value)", "split": "test", **metrics(y_te, med)})

    for name, build in CANDIDATES.items():
        m = build().fit(X_tr, y_tr)
        fitted[name] = m
        for s, Xs, ys in [("validation", X_va, y_va), ("test", X_te, y_te)]:
            rows.append({"model": name, "split": s, **metrics(ys, m.predict(Xs))})
        cv = cross_val_score(build(), X_tr, y_tr, cv=KFold(5, shuffle=True, random_state=SEED), scoring="r2")
        rows.append({"model": name, "split": "5-fold CV on train", "R2_log": cv.mean(), "R2_log_sd": cv.std()})

    res = pd.DataFrame(rows)
    res.to_csv(OUT / "model_comparison.csv", index=False)
    pd.set_option("display.width", 220)
    print(res.round(3).to_string(index=False))

    te = train_df.loc[X_te.index]
    bands = pd.cut(np.exp(y_te), [0, 1e6, 1e7, 2e8], labels=["< EUR 1M", "EUR 1M-10M", "> EUR 10M"])
    breakdown = []
    for name, m in fitted.items():
        p = pd.Series(m.predict(X_te), index=X_te.index)
        for g in ["GK", "DEF", "MID", "FWD"]:
            mask = te["position_group"] == g
            breakdown.append({"model": name, "group": g, "n": int(mask.sum()), **metrics(y_te[mask], p[mask])})
        for b in bands.cat.categories:
            mask = bands == b
            breakdown.append({"model": name, "group": b, "n": int(mask.sum()), **metrics(y_te[mask], p[mask])})
    bd = pd.DataFrame(breakdown)
    bd.to_csv(OUT / "error_breakdown.csv", index=False)
    print(bd.round(3).to_string(index=False))

    rf = fitted["Random forest"]
    names = [n.split("__")[-1] for n in rf.named_steps["pre"].get_feature_names_out()]
    imp = pd.Series(rf.named_steps["model"].feature_importances_, index=names).sort_values(ascending=False)
    imp.to_csv(OUT / "rf_feature_importance.csv", header=["importance"])
    print(imp.head(12).round(3).to_string())
    print("ridge alpha", fitted["Linear regression (ridge)"].named_steps["model"].alpha_)


if __name__ == "__main__":
    main()
