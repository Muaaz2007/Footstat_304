# Backend service

The backend is the runtime side of the system. It reads the prediction table that the AI
subsystem produces and serves it to the dashboard as JSON.

```
Dashboard  ->  backend API (this folder)  ->  ai-core/outputs/player_predictions.csv
```

It never trains a model. Training and evaluation belong to the offline AI pipeline in
`ai-core/`, as described in the architecture document.

## Why the standard library only

The AI subsystem needs pandas and scikit-learn, which are large dependencies. The backend
does not: it only has to read a CSV and answer HTTP requests. Using `csv` and
`http.server` from the standard library means the backend runs on any machine that has
Python 3.9 or newer, with no installation step. That is also one less thing that can break
during the demo.

## Structure

| Path | Responsibility |
| --- | --- |
| `backend/data/loader.py` | Reads `player_predictions.csv`, converts values to the right types, and validates the file against the interface contract |
| `backend/data/queries.py` | Search, filter, sort, paginate and summarise the loaded players |
| `backend/api.py` | HTTP routes, JSON responses, error handling and CORS |
| `backend/tests/` | Unit tests for the data layer and the API |

## Running it

From the project root:

```bash
python -m backend.api
```

Options:

```bash
python -m backend.api --host 127.0.0.1 --port 8000
python -m backend.api --data path/to/player_predictions.csv
```

The default data source is `ai-core/outputs/player_predictions.csv`. If that file is
missing, the server refuses to start and says so, rather than serving an empty dashboard.

## Routes

| Route | What it returns |
| --- | --- |
| `GET /` | Short description of the API and its routes |
| `GET /api/health` | Service status, number of players loaded, data source path |
| `GET /api/meta` | Filter values, sortable columns, maximum page size, field meanings |
| `GET /api/summary` | Totals, evaluation counts, position-group counts, average values, top movers |
| `GET /api/players` | Searchable, filterable, sortable, paginated player list |
| `GET /api/players/{player_id}` | One player's full evaluation |
| `GET /api/players/lookup?name=&birth_date=` | Players matching a name, optionally narrowed by birth date |

### `POST /api/predict` (live prediction)

Scores one player from a set of attributes, using the trained model in
`ai-core/market_value_model.joblib`. Use it for a player who is not in the prediction table,
or to explain a single prediction. This is the **only** route that needs the AI dependencies
(pandas, scikit-learn, joblib); without them it answers `503` with an explanation and every
other route keeps working.

Body:

```json
{
  "features": {
    "age": 27, "height_cm": 180, "weight_kgs": 75,
    "overall_rating": 84, "potential": 86, "potential_gap": 2,
    "position_group": "FWD", "preferred_foot": "Right"
  },
  "actual_value_eur": 45000000
}
```

Every feature name the model was trained with must be present; the list is 40 names and it
is stored inside the bundle (`bundle["features"]`). `actual_value_eur` is optional: without
it you get a prediction with no comparison.

```bash
curl -s -X POST http://127.0.0.1:8000/api/predict \
  -H "Content-Type: application/json" \
  -d '{"features": {"age": 27}}'
```

Response (abridged; the numbers depend on the model release):

```json
{
  "prediction": {
    "actual_value_eur": null,
    "predicted_value_eur": 29354000.0,
    "value_difference_eur": null,
    "relative_difference": null,
    "evaluation": "No recorded value",
    "prediction_type": "live model",
    "threshold_k_log": 0.08063261758267146
  },
  "source": "ai/live_inference.py"
}
```

| Situation | Status | Code |
| --- | --- | --- |
| Predicted | `200` | - |
| Missing or invalid JSON body | `400` | `bad_request` |
| `features` missing, empty, or a feature absent | `400` | `bad_request` |
| `actual_value_eur` not a number | `400` | `bad_request` |
| AI dependencies or model bundle not installed | `503` | `live_inference_unavailable` |
| Another path | `404` | `not_found` |

The bundle is loaded once and kept in memory, so the first prediction is slower than the
rest.

### Query parameters for `GET /api/players`

| Parameter | Meaning |
| --- | --- |
| `search` | Words matched against name, full name, nationality, positions and position group. Every word must match. |
| `position_group` | `GK`, `DEF`, `MID` or `FWD` |
| `evaluation` | `Potentially Undervalued`, `Fairly Valued`, `Potentially Overvalued`, `No recorded value` |
| `sort` | Any column listed in `GET /api/meta`; default `player_id` |
| `order` | `asc` (default) or `desc` |
| `limit` | Page size, 1 to 200; default 50 |
| `offset` | Number of players to skip; default 0 |

Example:

```
GET /api/players?position_group=FWD&evaluation=Potentially%20Undervalued&sort=relative_difference&order=desc&limit=20
```

### Response shape

```json
{
  "total": 17954,
  "count": 20,
  "limit": 20,
  "offset": 0,
  "results": [ { "player_id": 1, "name": "L. Messi", "...": "..." } ]
}
```

`total` is the number of players matching the filters; `count` is how many are in this
page. The dashboard needs both to build pagination.

### Errors

Errors always come back as JSON with an HTTP status that matches the problem:

| Status | When |
| --- | --- |
| 400 | Invalid parameter, such as an unknown sort column or a page size above 200 |
| 404 | Unknown route, or a `player_id` that does not exist |
| 500 | The data file does not match the expected schema |
| 503 | The prediction table is not there yet |

```json
{ "error": { "status": 404, "code": "not_found", "message": "No player with player_id=999999" } }
```

CORS is enabled for `GET` and `OPTIONS` so the dashboard can call the API directly during
development.

## Tests

```bash
python -m unittest discover -s backend/tests -t . -v
```

The tests cover loading and validation, the query logic, and the HTTP routes. They run
against the real prediction table, so they also act as a check that the AI output still
matches the interface contract.

## Data contract

The backend depends on the column names documented in
`ai-core/INTERFACE_FOR_DASHBOARD.md`. If the AI side renames a column, loading fails with a
message naming the missing column, instead of quietly serving wrong values.

The evaluation labels themselves are an AI-based indication, not a market fact. See
`ai-core/MARKET_VALUE_LIMITATION_AND_STRATEGY.md`.
