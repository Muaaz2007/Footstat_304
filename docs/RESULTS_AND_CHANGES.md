# Results and changes

What was built in this piece of work, why, how it was checked, and what is still open. Written
for the group and for the report: every number here was produced by running the code, not
estimated.

Work covered the **backend**, the **data/reference pipeline** and the **AI runtime layer**.
The `frontend/` folder was deliberately left untouched.

## 1. Summary

| Area | Before | Now |
| --- | --- | --- |
| Backend | empty folder | service with 8 routes, 39 tests, verified over HTTP |
| AI runtime | model file only | `ai/live_inference.py` scoring single players, 6 tests |
| AI documentation | prototype notes | buffer/threshold math, interface contract, limitation strategy |
| Data | unclear where files live | documented layout, reference-value pipeline, raw-data instructions |
| Frontend contract | none | `backend/README.md` + Streamlit integration guide |

## 2. Backend (`backend/`)

| File | What it does |
| --- | --- |
| `backend/data/loader.py` | Loads `player_predictions.csv`, converts every column to the right type, validates the file against the interface contract, indexes players by ID |
| `backend/data/queries.py` | Search, filter, sort, paginate, summarise, name lookup, and the filter metadata the dashboard needs |
| `backend/api.py` | JSON HTTP API on the standard library server; one exception-mapping path, CORS, `GET /api/predict` companion |
| `backend/tests/test_data_layer.py` | 15 tests: loading, validation, queries |
| `backend/tests/test_api.py` | 24 tests: routes against a real server on an ephemeral port |
| `backend/README.md` | Routes, parameters, response shapes, error codes |

Design decisions worth stating in the report:

- **Standard library only.** The runtime side reads a CSV and answers HTTP; it does not need
  pandas. Result: the backend runs with no installation, which removes a failure point in the
  demo and does not affect the AI side.
- **Validate on load, fail loudly.** Column names are a contract between the AI output and the
  runtime. A renamed column or invalid value stops the service with a message naming the
  problem, instead of showing wrong numbers on the dashboard.
- **Queries separated from HTTP.** The query logic is unit-tested without starting a server,
  and it stays reusable if the interface changes.
- **Ambiguous names return every match.** The interface document warns that short names are
  not unique, so the lookup route never silently picks one player.

### Routes

| Route | Purpose |
| --- | --- |
| `GET /` | API description and route list |
| `GET /api/health` | Status, player count, data source path |
| `GET /api/meta` | Filter values, sortable columns, maximum page size |
| `GET /api/summary` | Totals, evaluation counts, position counts, averages, top movers |
| `GET /api/players` | Search, filter, sort, paginate |
| `GET /api/players/{id}` | One player's full evaluation |
| `GET /api/players/lookup` | Name lookup, deliberately returning several matches |
| `POST /api/predict` | Score one player with the trained model (needs AI dependencies) |

`POST /api/predict` is the one route that bridges the two layers. It imports
`ai/live_inference` lazily, so a machine without pandas or scikit-learn still serves every
other route; the predict route then answers `503` with the reason. The model bundle is
loaded once and cached, because it is about 47 MB.

## 3. AI runtime (`ai/`)

| File | What it does |
| --- | --- |
| `ai/live_inference.py` | Loads the saved bundle, scores one player, applies the same threshold rule as the prototype |
| `ai/tests/test_live_inference.py` | 6 tests; skip themselves when pandas or joblib is absent |
| `ai/README.md` | Role, requirements, examples, test command |

Three real defects were found by actually running it, not by reading it:

1. **Wrong bundle path.** The module looked in `ai-core/outputs/market_value_model.joblib`;
   the bundle is at `ai-core/market_value_model.joblib`. It now checks both and names the
   paths it tried.
2. **String values crashed the model call.** Values arriving from a CSV or a JSON request are
   now coerced, so the backend route works without the caller re-typing the record.
3. **The arithmetic did not add up.** The difference was computed from the unrounded
   prediction while the displayed value was rounded to thousands, so
   `predicted - actual != shown difference` (265.51 EUR off on one test player). The
   difference and ratio are now derived from the reported value, matching the prediction
   table.

Verified on real players from the dataset:

| Player | Recorded | Live prediction | Evaluation |
| --- | --- | --- | --- |
| L. Messi | 110,500,000 | 97,694,000 | Potentially Overvalued |
| S. Gnabry | 34,000,000 | 33,538,000 | Fairly Valued |
| J. Castillo | 375,000 | 373,000 | Fairly Valued |
| A. Granqvist | no value | 8,972,000 | No recorded value |

The live numbers differ from `player_predictions.csv` for the same player by design: the
table holds out-of-fold predictions (a model that never saw the player), the live path uses
the final model trained on everyone. The table answers "how did the model do on this player",
the live path answers "what does the model say about this profile".

## 4. The threshold math and buffer (`ai-core/BUFFER_MATH_AND_VALUE_CHECK.md`)

The evaluation is a ratio test in log space, `r = log(predicted / actual)`, because values run
from thousands to hundreds of millions and a fixed euro gap means nothing across that range.

```
k = 2 x robust sigma of out-of-fold log error = 0.094925
exp(+k) = 1.0996   -> Potentially Undervalued if predicted >= 1.0996 x actual
exp(-k) = 0.9094   -> Potentially Overvalued if predicted <= 0.9094 x actual
band width = 19.01%
```

The buffer is **about +/-10% of the player's value**, not a fixed amount:

| Recorded value | Fair band | Buffer |
| --- | --- | --- |
| 1,000,000 | 909,441 .. 1,099,576 | +/- 99,576 |
| 10,000,000 | 9,094,412 .. 10,995,763 | +/- 995,763 |
| 34,000,000 | 30,921,002 .. 37,385,593 | +/- 3,385,593 |
| 110,500,000 | 100,493,256 .. 121,503,179 | +/- 11,003,179 |

The tradeoff, measured by recomputing the labels at each width:

| Buffer | k | Players flagged | Share |
| --- | --- | --- | --- |
| 1 sigma | 0.0475 | 6,393 | 36.1% |
| **2 sigma (used)** | **0.0949** | **2,405** | **13.6%** |
| 3 sigma | 0.1424 | 1,154 | 6.5% |
| 4 sigma | 0.1898 | 691 | 3.9% |

Model error on the 17,699 valued players: median 3.33%, 90th percentile 11.20%, 88% within
+/-10%. The buffer sits where the error tail starts, which is the argument for 2 sigma.

## 5. Then vs now: how old is the "actual" value

The dataset has no live market value, so the report needs to quantify how much the recorded
value has aged. Three scripts were added, standard library only apart from the optional
Apify client:

| Step | File | What it does |
| --- | --- | --- |
| 1 | `ai-core/ai/fetch_current_values.py` | Calls the Apify Transfermarkt Actor; refuses to run without `APIFY_API_TOKEN`, prints the cost estimate first |
| 2 | `ai-core/ai/build_reference_values.py` | Parses `"28.00M€"`, `"€1.20bn"`, `"€950k"` into euros, matches by name similarity, **refuses weak matches**; `--template` writes a hand-fillable sheet |
| 3 | `ai-core/ai/compare_then_now.py` | Joins to the prediction table, applies the same `k`, reports drift and whether labels change |

`ai-core/data/reference/players_to_check.csv` holds 24 players chosen for coverage: the 16
most valuable, 6 defenders, and 2 with no recorded value.

Tested end to end with a synthetic fixture: parsing produced 25,000,000 EUR, the matcher
correctly refused 23 names it could not verify, and the comparison reported `-77.38%` drift
with the label flipping from Overvalued to Undervalued.

**Not yet filled:** `data/reference/current_values.csv` is generated and empty. The values must
come from a source the group can cite. `footballtransfers.com` returns **403** to automated
requests, so its numbers have to be copied by hand (a few minutes for 24 rows) or fetched
through the paid Actor (about $0.018). No values were invented.

## 6. Documentation added

| Document | Purpose |
| --- | --- |
| `README.md` (root) | Whole system, folder layout, how to run the backend |
| `ai-core/README.md` | AI prototype, plus the buffer in numbers |
| `ai-core/BUFFER_MATH_AND_VALUE_CHECK.md` | The math, the buffer, the tradeoff, the then/now check |
| `ai-core/MARKET_VALUE_LIMITATION_AND_STRATEGY.md` | The data limitation and why a buffer is used |
| `ai-core/INTERFACE_FOR_DASHBOARD.md` | Column-by-column contract |
| `ai-core/data/raw/README.md` | The missing raw dataset, and how to restore it |
| `ai-core/data/reference/README.md` | How to collect current values (manual and automated) |
| `backend/README.md` | Routes, parameters, errors, `POST /api/predict` |
| `ai/README.md` | Live inference module |
| `data/README.md` | Where each data file lives and why there is one copy |
| `docs/IMPLEMENTATION_NOTES.md` | Backend/AI implementation record |
| `docs/FRONTEND_INTEGRATION_STREAMLIT.md` | Streamlit hand-off with working code |
| `docs/RESULTS_AND_CHANGES.md` | This file |
| `docs/Footstat_304_Documentation_Pack.docx` | Word pack for the documentation lead: 18 sections, 32 tables, every verified number, the report structure and a pre-submission checklist |

## 7. Verification

| Check | Command | Result |
| --- | --- | --- |
| Backend tests | `python -m unittest discover -s backend/tests -t .` | **39 tests, OK** on a bare Python and on the venv |
| Live inference tests | `.venv/Scripts/python -m unittest discover -s ai/tests -t .` | **6 tests, OK** |
| Prototype suite | `.venv/Scripts/python -m pytest ai-core/tests -q` | **7 passed** (raw dataset now included) |
| Compile | `python -m compileall backend ai ai-core/ai` | clean |
| Live HTTP | `python -m backend.api` + requests | health/player/summary 200; bad sort and limit 400; unknown player 404; `POST /api/predict` 200 with a real record, 400 on missing body or features, 404 on an unknown POST route |

## 8. Still open

| # | Item | Effect | Owner |
| --- | --- | --- | --- |
| 1 | ~~raw dataset absent~~ **resolved**: `ai-core/data/raw/fifa_players.csv` is committed | pipeline can be re-run and retrained; all 7 prototype tests run | done |
| 2 | `data/reference/current_values.csv` is empty | the then/now drift claim has no numbers yet | data owner |
| 3 | ~~Dashboard not built~~ **resolved**: `frontend/` — five pages, dark theme, player photographs, live API or labelled offline snapshot | a working interface, verified in `docs/VERIFICATION_AND_SCREENSHOTS.md` | done |
| 4 | No authentication | fine for a local demo; must be stated, not implied | known limitation |
| 5 | Model bundle untracked from git | regenerable; keeps the repository small | handled here |

Item 1 was the only real risk to the submission, and it is now closed: see section 10.

## 9. Honest limitations to state in the report

- The recorded value is a snapshot, not a live price; the labels are model-based indications.
- The model is accurate against that snapshot (median 3.33% error) but the snapshot's age is a
  separate source of error, which the then/now check is designed to measure.
- The 255 players with no recorded value get a prediction and the label "No recorded value" —
  no comparison is invented for them.
- Live prediction needs the AI dependencies installed; the dashboard's main path does not.

## 10. Reproduction run (raw dataset restored)

The raw dataset was obtained from Kaggle (`maso0dahmed/football-players-data`, "Football
Players Data", from sofifa.com), committed to `ai-core/data/raw/fifa_players.csv`, and used to
re-run the whole AI pipeline from scratch.

### File check before running

| Check | Expected | Found |
| --- | --- | --- |
| Rows | 17,954 | 17,954 |
| Columns | 51 (52 after `player_id` is added) | 51 |
| Players with no recorded value | 255 | 255 |
| Corrupted heights still present | yes (raw file) | yes |
| Columns `release_clause_euro`, `wage_euro`, `body_type`, national team | present | present |

### Pipeline output vs the previously committed results

| Output | Result |
| --- | --- |
| `thresholds.json` | **byte-identical** — `k_log = 0.09492490316094522`, `robust_sigma = 0.04746245158047261` |
| `player_predictions.csv` | **byte-identical** |
| `players_clean.csv` | **byte-identical** |
| Label counts | 15,329 Fairly Valued / 1,199 Potentially Undervalued / 1,171 Potentially Overvalued / 255 no value — identical |
| `model_comparison.csv`, `error_breakdown.csv`, `rf_feature_importance.csv` | identical to the 9th significant digit, differences only in the 10th+ (e.g. RF test MAE 163,687.36096015**494** vs ...**474**) — floating-point noise between library builds, not a different model |
| Prototype tests | **7 passed, 0 skipped** |

The conclusion for the report is now a verified claim rather than an intention: **the AI
subsystem is reproducible from the committed raw data with the pinned dependency versions.**
The thresholds, the evaluation table and every headline metric regenerate exactly.
