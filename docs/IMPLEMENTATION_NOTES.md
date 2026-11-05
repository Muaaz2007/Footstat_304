# Implementation notes

This note records what was built in the backend and AI runtime parts of the system, the
reasoning behind each decision, how it was checked, and what is still outstanding. It is
written to be read alongside `README.md` and the AI subsystem documents.

## 1. Where this work fits in the system

The architecture document splits the system into two processes:

- **Offline AI development**: dataset -> processing -> feature selection -> training ->
  comparison -> predictions -> `player_predictions.csv`
- **Runtime application**: user -> dashboard -> player selection -> prediction table ->
  player results

The offline half already existed in `ai-core/`. The missing half was the runtime path: a
service that reads the prepared prediction table and answers requests about players. That
is what this work adds.

## 2. What was built

| File | What it does |
| --- | --- |
| `backend/data/loader.py` | Loads `player_predictions.csv`, converts each column to the correct type, validates the file against the interface contract, and indexes players by ID |
| `backend/data/queries.py` | Search, filter, sort, paginate, summarise, name lookup, and the metadata the dashboard needs for its filters |
| `backend/api.py` | JSON HTTP API with seven read routes plus `POST /api/predict` for live scoring, consistent error responses, and CORS for the dashboard |
| `backend/tests/test_data_layer.py` | Unit tests for loading, validation and query behaviour |
| `backend/tests/test_api.py` | Tests that start the real server and call it over HTTP |
| `ai/live_inference.py` | Loads the saved model bundle and scores one player on demand, using the same threshold rule as the prototype |
| `backend/README.md`, `ai/README.md`, `data/README.md` | Documentation for each part |
| `README.md` (project root) | Updated to describe the runtime parts and how to run them |

## 3. Why these decisions were made

**Standard library only in the backend.**
The AI subsystem needs pandas and scikit-learn. The backend only needs to read a CSV and
answer HTTP requests, so it uses `csv` and `http.server`. The benefit is that the runtime
part runs on any machine with Python installed, with nothing to install and one less thing
to fail during a demonstration.

**The prediction table is validated on load.**
The backend depends on column names that the AI subsystem produces. If a column is renamed
or a value is invalid, loading stops with a message naming the problem. The alternative —
serving whatever is in the file — would show wrong numbers on the dashboard without any
warning.

**Queries are separated from the HTTP layer.**
All filtering, sorting and pagination live in `queries.py`, and the HTTP handler only
converts parameters and formats responses. This means the query logic is unit-tested
directly, without starting a server, and it stays reusable if the interface changes.

**Ambiguous name lookups return every match.**
The interface document warns that short names are not unique. The lookup route therefore
returns all matches, with a note telling the caller to use `player_id`, instead of silently
picking one player and possibly showing the wrong evaluation.

**Live prediction is separated from the prepared table.**
Normal dashboard use reads the prepared table: fast, and no machine-learning libraries
needed. The `ai/live_inference.py` module covers the other case — a player not in the table
— and raises a clear error if the dependencies or the trained model are missing, rather
than returning an unqualified guess.

**Evaluation labels keep their original meaning.**
The backend does not reinterpret the labels. It only serves them. The reason the labels are
an indication rather than a valuation is documented in
`ai-core/MARKET_VALUE_LIMITATION_AND_STRATEGY.md`, which also records the threshold-based
tradeoff used because the dataset has no live market value.

## 4. How it was verified

- `python -m compileall backend ai ai-core` — all modules compile.
- `python -m unittest discover -s backend/tests -t .` — 39 tests covering the data layer,
  the queries and the API routes.

The tests check behaviour that matters for the interface:

- all 17,954 players load and are unique by `player_id`
- a missing file and a missing column are both reported clearly
- an invalid predicted value is rejected
- search, filters and pagination return consistent totals
- sorting puts players with no recorded value last, in both directions
- summary counts add up to the total number of players
- the API returns 200, 400 and 404 as documented, with the CORS header present
- unknown routes and unknown players return JSON errors rather than HTML

Because the tests run against the real prediction table, they also act as a check that the
AI output still matches the interface contract.

### Live inference, run against the real model

`ai/live_inference.py` was run in a local virtual environment (`python -m venv .venv`,
`pip install -r ai-core/requirements.txt`) using the saved bundle and real players from
`ai-core/data/processed/players_clean.csv`:

| Player | Recorded value | Live prediction | Evaluation |
| --- | --- | --- | --- |
| L. Messi | 110,500,000 | 97,694,000 | Potentially Overvalued |
| S. Gnabry | 34,000,000 | 33,538,000 | Fairly Valued |
| J. Castillo | 375,000 | 373,000 | Fairly Valued |
| A. Granqvist | no value | 8,972,000 | No recorded value |

The live numbers differ from `player_predictions.csv` for the same player, and that is
expected: the table holds out-of-fold predictions (a model that never saw the player),
while the live path uses the final model trained on all valued players. Live inference
answers "what does the model say about this attributes profile", not "how did the model do
on this player". Both are correct; they answer different questions.

Three problems were found and fixed while doing this:

- the saved bundle sits in `ai-core/`, not `ai-core/outputs/`, so the module now looks in
  both places instead of failing on the documented path
- the module now accepts numeric strings, so a record read from a CSV or a JSON request
  works without extra conversion
- the difference was calculated from the unrounded prediction while the reported value was
  rounded to thousands, so `predicted - actual` did not equal the shown difference. The
  difference and ratio are now derived from the reported value, as the prediction table
  does, so the dashboard's numbers add up

### Version caveat (closed)

The bundle is trained with scikit-learn 1.8.0 and `ai-core/requirements.txt` pins 1.8.0, so
the `InconsistentVersionWarning` recorded here no longer appears. The pipeline was re-run
from `ai-core/data/raw/fifa_players.csv` (now committed) and reproduced `thresholds.json`,
`player_predictions.csv` and `players_clean.csv` byte for byte — see
`docs/RESULTS_AND_CHANGES.md` section 10.

### Live inference tests

`ai/tests/test_live_inference.py` covers the bundle contents, the threshold rule at its
boundaries, the shape of the result, a player with no recorded value, a missing feature and
a missing bundle. They skip themselves when pandas or joblib is absent *and* when the
trained bundle has not been built (`unittest.SkipTest` in `setUpClass`), so a fresh clone
reports *skipped* rather than a setup error, and the backend suite still runs on a machine
without the AI dependencies.

Final state of the checks:

| Command | Result |
| --- | --- |
| `python -m unittest discover -s backend/tests -t .` | 39 tests, OK (no AI dependencies needed) |
| `.venv/Scripts/python -m unittest discover -s ai/tests -t .` | 6 tests, OK |
| `.venv/Scripts/python -m pytest ai-core/tests -q` | 7 passed (the raw dataset is committed) |
| `python -m backend.api` then HTTP requests | health, player, summary return 200; bad sort and limit return 400; unknown player returns 404; `POST /api/predict` returns 200 for a real record |

## 5. What remains

- **Frontend**: built. `frontend/` holds five pages (Overview, Player Explorer, Player
  Profile, Compare, Model & Method) with a dark editorial theme, player photographs and a
  labelled offline fallback. See `docs/VERIFICATION_AND_SCREENSHOTS.md`.
- **Dashboard and API in one command**: still two terminals; the wiring belongs in the
  frontend, and a wrapper script is the obvious next step.
- **Version pinning for the model bundle**: decide whether to pin scikit-learn to 1.8.x or
  regenerate the bundle, so results stay reproducible.
- **Serving the dashboard from one place**: the API and the frontend currently run
  separately. If the finished product should start with a single command, that wiring
  belongs in the frontend work.

## 6. Known limitations

- The dataset is a snapshot. The system compares against recorded values, not live prices,
  and says so in the evaluation notes.
- Search is a simple substring match. It is predictable and adequate for the dataset size,
  but it does not handle spelling mistakes.
- The backend holds the table in memory, which is appropriate for 17,954 rows and keeps the
  code simple.
