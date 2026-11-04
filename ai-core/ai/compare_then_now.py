"""Compare the dataset's recorded values ("then") with current values ("now").

Why this exists
---------------
The dataset has no live market value: its `actual_value_eur` is a snapshot. The
evaluation in `player_predictions.csv` therefore measures the model against that
snapshot. This script measures something different and useful for the report: how
much the snapshot has drifted from today's market, and whether the evaluation
labels would change if current values were used instead.

Inputs
------
* `data/reference/current_values.csv` - built by `build_reference_values.py` from
  the Apify / Transfermarkt scrape. Only a sample of players is needed.
* `outputs/player_predictions.csv` - the evaluation table.
* `outputs/thresholds.json` - so the same buffer rule is applied.

Output
------
* `outputs/then_now_comparison.csv` - one row per matched player.
* A printed summary with the drift and how many labels changed.

Standard library only, so it runs without pandas.

Usage (from ai-core/)
---------------------
    python ai/compare_then_now.py
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS = ROOT / "outputs" / "player_predictions.csv"
THRESHOLDS = ROOT / "outputs" / "thresholds.json"
REFERENCE = ROOT / "data" / "reference" / "current_values.csv"
OUT = ROOT / "outputs" / "then_now_comparison.csv"

UNDER = "Potentially Undervalued"
FAIR = "Fairly Valued"
OVER = "Potentially Overvalued"
NONE = "No recorded value"

COLUMNS = [
    "player_id",
    "name",
    "dataset_value_eur",
    "current_value_eur",
    "value_drift_pct",
    "predicted_value_eur",
    "prediction_vs_dataset_pct",
    "prediction_vs_current_pct",
    "evaluation_then",
    "evaluation_now",
    "label_changed",
]


def classify(predicted: float, actual: float | None, k: float) -> str:
    if actual is None or actual <= 0:
        return NONE
    ratio = math.log(predicted / actual)
    if ratio > k:
        return UNDER
    if ratio < -k:
        return OVER
    return FAIR


def number(value):
    """Empty strings and None mean 'not available'."""
    if value is None or value == "":
        return None
    return float(value)


def percent(numerator: float, denominator: float) -> float | None:
    if not denominator:
        return None
    return round((numerator / denominator - 1) * 100, 2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    parser.add_argument("--predictions", type=Path, default=PREDICTIONS)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    if not args.reference.exists():
        raise SystemExit(
            f"No current values at {args.reference}.\n"
            "Run python ai/fetch_current_values.py, then python ai/build_reference_values.py."
        )

    k = float(json.loads(THRESHOLDS.read_text(encoding="utf-8"))["k_log"])

    with open(args.predictions, newline="", encoding="utf-8") as handle:
        predictions = {row["player_id"]: row for row in csv.DictReader(handle)}
    with open(args.reference, newline="", encoding="utf-8") as handle:
        reference = list(csv.DictReader(handle))

    rows, skipped = [], []
    for ref in reference:
        table = predictions.get(ref["player_id"])
        if table is None:
            skipped.append(ref.get("dataset_name") or ref["player_id"])
            continue

        then = number(table["actual_value_eur"])
        now = number(ref["current_value_eur"])
        predicted = number(table["predicted_value_eur"])
        if now is None or predicted is None:
            skipped.append(ref.get("dataset_name") or ref["player_id"])
            continue

        evaluation_then = table["evaluation"]
        evaluation_now = classify(predicted, now, k)

        rows.append(
            {
                "player_id": ref["player_id"],
                "name": table["name"],
                "dataset_value_eur": "%.0f" % then if then else "",
                "current_value_eur": "%.0f" % now,
                "value_drift_pct": "" if then is None else percent(now, then),
                "predicted_value_eur": "%.0f" % predicted,
                "prediction_vs_dataset_pct": percent(predicted, then) if then else "",
                "prediction_vs_current_pct": percent(predicted, now),
                "evaluation_then": evaluation_then,
                "evaluation_now": evaluation_now,
                "label_changed": "yes" if evaluation_then != evaluation_now else "no",
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    report(rows, skipped, k, args.out)


def report(rows, skipped, k, out_path: Path) -> None:
    print(f"Compared {len(rows)} player(s); skipped {len(skipped)}")
    if skipped:
        print("  skipped: " + ", ".join(skipped[:8]) + (" ..." if len(skipped) > 8 else ""))
    if not rows:
        print("Nothing to compare. Check player_id values in current_values.csv.")
        return

    drifts = [row["value_drift_pct"] for row in rows if row["value_drift_pct"] != ""]
    vs_dataset = [abs(row["prediction_vs_dataset_pct"]) for row in rows
                  if row["prediction_vs_dataset_pct"] != ""]
    vs_current = [abs(row["prediction_vs_current_pct"]) for row in rows
                  if row["prediction_vs_current_pct"] != ""]
    changed = sum(1 for row in rows if row["label_changed"] == "yes")

    print("\n--- How much the dataset values have moved (then -> now) ---")
    if drifts:
        print(f"median drift : {statistics.median(drifts):+.1f}%")
        print(f"mean drift   : {statistics.mean(drifts):+.1f}%")
        print(f"rose / fell  : {sum(1 for d in drifts if d > 0)} / {sum(1 for d in drifts if d < 0)}")

    print("\n--- How well the model does against each reference ---")
    if vs_dataset:
        print(f"vs dataset value : median absolute gap {statistics.median(vs_dataset):.1f}%")
    if vs_current:
        print(f"vs current value : median absolute gap {statistics.median(vs_current):.1f}%")

    print("\n--- The buffer, at the median current value ---")
    values = sorted(float(row["current_value_eur"]) for row in rows)
    mid = statistics.median(values)
    print(f"median current value : {mid:,.0f}")
    print(f"fair band            : {mid * math.exp(-k):,.0f} .. {mid * math.exp(k):,.0f}")
    print(f"buffer               : +- {mid * (math.exp(k) - 1):,.0f} "
          f"({(math.exp(k) - 1) * 100:.2f}% / {(1 - math.exp(-k)) * 100:.2f}%)")

    print("\n--- Would the labels change? ---")
    print(f"labels changed : {changed} of {len(rows)} ({changed / len(rows) * 100:.0f}%)")
    for label in (UNDER, FAIR, OVER):
        then = sum(1 for row in rows if row["evaluation_then"] == label)
        now = sum(1 for row in rows if row["evaluation_now"] == label)
        print(f"  {label:<25} then {then:>3} -> now {now:>3}")

    print(f"\nSaved: {out_path}")
    print("Read this as: the model is stable against the snapshot, and current values "
          "show how much that snapshot has aged.")


if __name__ == "__main__":
    main()
