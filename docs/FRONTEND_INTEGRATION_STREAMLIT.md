# Connecting the Streamlit dashboard to the backend

This is the hand-off for the frontend team. The backend is already running and documented;
this page shows how to call it from Streamlit, which pieces to use, and the mistakes that
will cost you an evening.

## 1. The shape of the system

```
Streamlit app  --HTTP-->  backend API  -->  ai-core/outputs/player_predictions.csv
      |
      +----- or, for a player not in the table:  POST /api/predict --> trained model
```

The dashboard never reads the CSV and never loads the model. It asks the API. That keeps
the 2.6 MB table and the 47 MB model out of the web process, and it means the AI team can
change the model without you changing any Streamlit code.

## 2. Run both services

```bash
# terminal 1 - backend (standard library only, no install needed)
python -m backend.api --port 8000

# terminal 2 - dashboard
streamlit run frontend/app.py
```

Check the API before blaming Streamlit:

```bash
curl -s http://127.0.0.1:8000/api/health
```

## 3. A small, reusable client

Put this in `frontend/api_client.py`. Every page imports from it, so the base URL and error
handling live in one place.

```python
"""Thin client for the Footstat_304 backend API."""
import os
import requests

API = os.environ.get("FOOTSTAT_API", "http://127.0.0.1:8000")
TIMEOUT = 15


class ApiError(RuntimeError):
    """The backend answered with an error, or could not be reached."""


def _get(path, **params):
    try:
        response = requests.get(f"{API}{path}", params=params, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise ApiError(f"Cannot reach the API at {API}. Is `python -m backend.api` running?") from exc
    if not response.ok:
        detail = response.json().get("error", {}).get("message", response.text)
        raise ApiError(f"{response.status_code}: {detail}")
    return response.json()


def _post(path, payload):
    try:
        response = requests.post(f"{API}{path}", json=payload, timeout=60)
    except requests.RequestException as exc:
        raise ApiError(f"Cannot reach the API at {API}.") from exc
    if not response.ok:
        detail = response.json().get("error", {}).get("message", response.text)
        raise ApiError(f"{response.status_code}: {detail}")
    return response.json()


def health():            return _get("/api/health")
def meta():              return _get("/api/meta")
def summary():           return _get("/api/summary")
def players(**params):   return _get("/api/players", **params)
def player(player_id):   return _get(f"/api/players/{player_id}")
def lookup(name):        return _get("/api/players/lookup", name=name)
def predict(features, actual_value_eur=None):
    body = {"features": features}
    if actual_value_eur is not None:
        body["actual_value_eur"] = actual_value_eur
    return _post("/api/predict", body)["prediction"]
```

`requests` comes with Streamlit's environment; if not, `pip install requests`.

## 4. Cache, but not too long

The prediction table only changes when the AI pipeline is re-run, so cache it. Do not cache
per keystroke.

```python
import streamlit as st
from api_client import summary, meta, players, ApiError

@st.cache_data(ttl=300, show_spinner=False)
def cached_meta():
    return meta()

@st.cache_data(ttl=300, show_spinner=False)
def cached_summary():
    return summary()
```

For the player list, cache on the exact query, using the parameters as the cache key:

```python
@st.cache_data(ttl=120, show_spinner=False)
def cached_players(search="", position_group=None, evaluation=None,
                   sort="player_id", order="asc", limit=50, offset=0):
    return players(search=search or None, position_group=position_group,
                   evaluation=evaluation, sort=sort, order=order,
                   limit=limit, offset=offset)
```

## 5. Build the filters from `/api/meta`, not from hard-coded lists

`/api/meta` returns the values the backend will actually accept. Hard-coding them is how the
dashboard ends up offering a filter that returns `400`.

```python
m = cached_meta()

position = st.sidebar.selectbox("Position group", ["All"] + m["position_groups"])
label = st.sidebar.selectbox("Evaluation", ["All"] + m["evaluations"])
sort_column = st.sidebar.selectbox("Sort by", m["sortable_columns"])
ascending = st.sidebar.radio("Order", ["Ascending", "Descending"]) == "Ascending"
```

Note `m["max_limit"]` — the API refuses `limit` above it (200). Page, do not ask for
everything at once.

## 6. The player table

```python
page_size = 50
page = st.number_input("Page", min_value=1, value=1, step=1)
offset = (page - 1) * page_size

result = cached_players(
    search=st.session_state.get("search", ""),
    position_group=None if position == "All" else position,
    evaluation=None if label == "All" else label,
    sort=sort_column,
    order="asc" if ascending else "desc",
    limit=page_size,
    offset=offset,
)

st.caption(f"{result['total']:,} players match - showing {result['count']} from {offset + 1}")

import pandas as pd
frame = pd.DataFrame(result["results"])
st.dataframe(
    frame[["player_id", "name", "age", "position_group", "overall_rating",
           "actual_value_eur", "predicted_value_eur", "relative_difference", "evaluation"]],
    hide_index=True,
    use_container_width=True,
    column_config={
        "actual_value_eur": st.column_config.NumberColumn("Recorded (EUR)", format="%,d"),
        "predicted_value_eur": st.column_config.NumberColumn("Predicted (EUR)", format="%,d"),
        "relative_difference": st.column_config.NumberColumn("Gap", format="%.2f"),
    },
)
```

`player_id` is the key to the detail page. Keep it in the table even if you hide it visually:
short names are not unique, and `/api/players/lookup?name=Messi` deliberately returns
several players.

## 7. The player detail page

```python
chosen = st.selectbox("Player", frame["player_id"],
                      format_func=lambda pid: frame.set_index("player_id").loc[pid, "name"])

detail = player(int(chosen))

left, right = st.columns(2)
left.metric("Recorded value", f"EUR {detail['actual_value_eur']:,.0f}"
            if detail["actual_value_eur"] else "no recorded value")
right.metric("Model estimate", f"EUR {detail['predicted_value_eur']:,.0f}")

st.write(f"Evaluation: **{detail['evaluation']}**")
st.write(f"Difference: {detail['value_difference_eur']:,.0f} EUR "
         f"({detail['relative_difference'] * 100:.1f}%)"
         if detail["value_difference_eur"] is not None else
         "No recorded value, so there is nothing to compare against.")
st.caption(f"Prediction type: {detail['prediction_type']}")
```

`actual_value_eur`, `value_difference_eur` and `relative_difference` are **`null`** for the
255 players with no recorded value. Test for `None` before formatting, or Streamlit shows
`NoneType` errors to your examiner.

## 8. The live prediction form

Only worth building if you want the "score a new player" feature. It needs the AI
dependencies installed on the machine running the backend, otherwise it answers `503`.

```python
with st.form("live"):
    age = st.number_input("Age", 15, 45, 25)
    overall = st.slider("Overall rating", 40, 99, 75)
    potential = st.slider("Potential", 40, 99, 80)
    group = st.selectbox("Position group", ["GK", "DEF", "MID", "FWD"])
    foot = st.selectbox("Preferred foot", ["Right", "Left"])
    submitted = st.form_submit_button("Predict")

if submitted:
    try:
        out = predict({"age": age, "overall_rating": overall, "potential": potential,
                       "potential_gap": potential - overall,
                       "position_group": group, "preferred_foot": foot})
        st.metric("Model estimate", f"EUR {out['predicted_value_eur']:,.0f}")
    except ApiError as exc:
        st.error(str(exc))
```

That call sends only 6 of the 40 features, so the backend answers `400` naming the ones it
is missing. That is intentional: the model was trained on all 40, and silently filling the
rest with zeros would produce a confident, meaningless number. Either collect all 40 in the
form, or drop the live-prediction page from the dashboard scope — the prepared table covers
every player in the dataset.

## 9. Error handling that survives the demo

```python
try:
    data = cached_summary()
except ApiError as exc:
    st.error(f"Backend unavailable: {exc}")
    st.stop()
```

Rules that avoid the common failures:

- Call `st.stop()` after a connection error, otherwise every widget below draws itself
  against `None` and the traceback hides the real message.
- Wrap API calls in `try/except ApiError`; a `400` from a bad filter should read as a
  message, not a stack trace.
- Never put `localhost` assumptions in three files. Use the `FOOTSTAT_API` environment
  variable from section 3.

## 10. Deployment notes

- If Streamlit and the API run on **different machines**, set `FOOTSTAT_API` to the API's
  address and start the backend with `--host 0.0.0.0`.
- CORS is already enabled (`Access-Control-Allow-Origin: *`) and is only relevant if you
  call the API from browser-side JavaScript. Server-side `requests` calls in Streamlit do
  not need it.
- The backend has no authentication. Put it on the same host or a private network, and say
  so in the report rather than implying it is secured.
- The API is read-only except `/api/predict`, which writes nothing.

## 11. Fallback if the API is down during the presentation

The dashboard can read the table directly, at the cost of duplicating the query logic:

```python
import pandas as pd
TABLE = "ai-core/outputs/player_predictions.csv"

@st.cache_data
def load_table():
    return pd.read_csv(TABLE)

df = load_table()
```

Use it as an emergency path only. Two sources of truth is exactly the problem the backend
was built to remove.

## 12. Checklist before you demo

- [ ] `python -m backend.api` running, `/api/health` returns `"status": "ok"`
- [ ] filters built from `/api/meta`, no hard-coded lists
- [ ] `limit` never above `meta["max_limit"]`
- [ ] `None` handled for the three comparison fields
- [ ] detail page uses `player_id`, not the name
- [ ] every API call wrapped, `st.stop()` on connection failure
- [ ] live prediction hidden or explained if the AI dependencies are not installed
