# The threshold math, the buffer, and the then/now value check

This note explains, with the project's real numbers, how the evaluation categories are
calculated, how big the buffer is, and how to check how much the dataset's recorded values
have aged since they were collected.

It is written to be defensible in a report: every number here comes from the project's own
output files, not from an estimate.

## 1. Why the comparison happens in log space

Market values are not spread evenly. In this dataset they run from a few thousand euros to
over one hundred million. A 1M error means something completely different to a player worth
500k than to one worth 100M.

So the comparison is made on the **ratio**, not on the raw difference:

```
r = log(predicted / actual)
```

Compressing to a log and multiplying back by the value is exactly how the percentage view
works:

- `r = 0` means the model and the recorded value agree exactly.
- `r = +0.10` means the model says about 10.5% more than the recorded value.
- `r = -0.10` means about 9.5% less.

Using `log` also makes the error distribution roughly symmetric and bell-shaped, which is
what allows a threshold to be set from the model's own error in section 3.

## 2. The rule

```
r >  +k   -> Potentially Undervalued
r <  -k   -> Potentially Overvalued
otherwise -> Fairly Valued
actual value missing -> No recorded value
```

`k` is the buffer. Everything inside `[-k, +k]` is treated as agreement, because a
difference smaller than the model's own noise is not evidence of anything.

## 3. Where k comes from

`k` is not chosen by taste. It is set from the model's own out-of-fold error:

```
k = 2 x robust sigma of (log prediction error)
```

- **Out-of-fold** means each player is predicted by a forest that never saw that player, so
  the error is honest rather than memorised.
- **Robust sigma** is `1.4826 x median absolute deviation`, which ignores the handful of
  extreme players that would inflate a standard deviation.
- **The factor 2** is the buffer width: two sigma covers roughly 95% of a normal
  distribution, so a difference inside it is ordinary model noise.

Measured values from `outputs/thresholds.json`:

| Quantity | Value |
| --- | --- |
| `robust_sigma_log` | 0.04746 |
| `k_sigma` | 2.0 |
| **`k_log`** | **0.09492** |
| `exp(+k)` | 1.0996 -> "at least 1.0996x the recorded value" |
| `exp(-k)` | 0.9094 -> "at most 0.9094x the recorded value" |

In plain words: **the model must disagree with the recorded value by about 10% before the
system calls a player under- or overvalued.**

## 4. How much buffer that actually is

The buffer is a percentage, so it scales with the player. That is deliberate: a fixed euro
buffer would be far too wide for a 500k player and far too narrow for a 100M player.

| Recorded value | Fair band (no label) | Buffer each side |
| --- | --- | --- |
| 500,000 | 454,721 .. 549,788 | +/- 49,788 |
| 1,000,000 | 909,441 .. 1,099,576 | +/- 99,576 |
| 5,000,000 | 4,547,206 .. 5,497,881 | +/- 497,881 |
| 10,000,000 | 9,094,412 .. 10,995,763 | +/- 995,763 |
| 50,000,000 | 45,472,061 .. 54,978,814 | +/- 4,978,814 |
| 100,000,000 | 90,944,123 .. 109,957,628 | +/- 9,957,628 |

The band is 19.01% wide in total (`exp(k) - exp(-k)`).

## 5. The tradeoff, stated with counts

The buffer is a tradeoff between two kinds of mistake, and this table is the evidence that
2 sigma is a reasonable place to sit:

| Buffer | k | Players flagged | Share flagged |
| --- | --- | --- | --- |
| 1 sigma (narrow) | 0.0475 | 6,393 | 36.1% |
| **2 sigma (used)** | **0.0949** | **2,405** | **13.6%** |
| 3 sigma (wide) | 0.1424 | 1,154 | 6.5% |
| 4 sigma (very wide) | 0.1898 | 691 | 3.9% |

Read the columns the other way and the tradeoff is obvious:

- At **1 sigma** nearly one player in three gets a label. Too many, and most of them are
  just noise.
- At **4 sigma** only 3.9% do. Defensible but almost useless: it misses real disagreements.
- At **2 sigma** the flagged set is small enough to be worth looking at, and each flag is
  larger than the model's own error by construction.

The shipped table (`outputs/player_predictions.csv`, using unrounded predictions) gives
15,329 Fairly Valued, 1,199 Potentially Undervalued, 1,171 Potentially Overvalued and 255
No recorded value. Recomputing from the rounded column gives 1,229 / 1,176, so the labels
sit within a few dozen players of any rounding choice — that is the size of the change a
rounding decision can cause, and it is small.

## 6. What the model's error looks like

From the same table, on all 17,699 players with a recorded value:

| Measure | Value |
| --- | --- |
| Median absolute percentage error | 3.33% |
| Mean absolute percentage error | 5.75% |
| 90th percentile error | 11.20% |
| Share within +/-5% | 66.57% |
| Share within +/-10% | 88.05% |

Two things follow. First, the buffer at ~10% lines up with where the model's own error
starts to matter: 88% of predictions are already inside +/-10%, so the label is doing work
only for the remaining tail. Second, the model is genuinely accurate against the snapshot,
which is why the snapshot's age (section 7) matters more than the model's error for how the
labels should be read.

The comparison of the two techniques is in `outputs/model_comparison.csv`: random forest has
a test MAE of about 163,687 EUR against 505,645 EUR for ridge regression, with 97.5% of test
predictions within 25% of the recorded value.

## 7. Then vs now: checking how old the "actual" is

The honest limitation of this project is that `actual_value_eur` is a snapshot, not a live
price. A useful, cheap validity check is to take a sample of players and look up their
**current** value, then ask two questions:

1. How far has the snapshot drifted from today's market?
2. Would the labels change if today's values were used instead?

### Where the current values come from

Transfermarkt, through the paid Apify Actor `data_xplorer/transfermarkt-api-scraper` (about
USD 0.75 per 1,000 results, so a 24-player sample costs well under one cent on top of the
Apify plan). The project does not scrape the site directly and stores no credentials in the
repository.

### The steps

```bash
pip install apify-client
export APIFY_API_TOKEN=...            # Apify Console -> Settings -> Integrations

cd ai-core
python ai/fetch_current_values.py     # calls the Actor, saves raw JSON with the fetch date
python ai/build_reference_values.py   # parses it into data/reference/current_values.csv
python ai/compare_then_now.py         # writes outputs/then_now_comparison.csv + summary
```

`data/reference/players_to_check.csv` already holds 24 players chosen to be useful: the most
valuable players, a spread across position groups, and two players with no recorded value so
the "No recorded value" path is exercised too.

### What the comparison outputs

`outputs/then_now_comparison.csv`, one row per player:

| Column | Meaning |
| --- | --- |
| `dataset_value_eur` | The snapshot value ("then") |
| `current_value_eur` | Today's value ("now") |
| `value_drift_pct` | How much the value moved, in percent |
| `predicted_value_eur` | The model's estimate ("then" model, unchanged) |
| `prediction_vs_dataset_pct` | Model against the snapshot |
| `prediction_vs_current_pct` | Model against today's value |
| `evaluation_then` / `evaluation_now` | The label under each reference |
| `label_changed` | Whether the buffer decision flips |

The summary also prints the drift median, the fair band in euros at the median current
value, and how many labels moved.

### How to write this up honestly

The correct claim is narrow and strong:

> The model's estimates sit close to the dataset's recorded values, and the evaluation
> labels are stable under a buffer sized from the model's own error. The recorded values
> themselves are a snapshot and have moved since collection; the comparison quantifies that
> drift rather than pretending it does not exist.

The incorrect claim, which the project must not make: that this is a live valuation system,
or that the labels are current transfer-market judgements.

## 8. Known limits of this check

- The sample is small by design. It demonstrates drift, it does not estimate it for all
  17,954 players.
- Name matching uses similarity and refuses weak matches, so a few players may come back
  unmatched and need a manual row. That is safer than attaching a value to the wrong player.
- Transfermarkt values are themselves estimates by a third party, not transaction prices.
- The Actor is a paid dependency; the scripts are optional and the rest of the system works
  without them.
