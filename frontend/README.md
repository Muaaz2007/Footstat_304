# Footstat 304 — Streamlit dashboard

Reads the prediction table from the backend API and presents it as five pages:
Overview, Player Explorer, Player Profile, Compare, Model & Method.

## Run it

```bash
# terminal 1 — the API (standard library only)
python -m backend.api --port 8000

# terminal 2 — the dashboard
streamlit run frontend/app.py
```

Open the URL Streamlit prints (usually <http://localhost:8501>).

The app also runs with the API stopped: it falls back to the committed CSV
snapshot and says so in the sidebar ("Offline snapshot"). That path exists for
demos, not as a second source of truth.

## Files

| File | Role |
| --- | --- |
| `app.py` | the five pages, data loading, routing |
| `api_client.py` | the only place that talks HTTP; base URL from `FOOTSTAT_API` |
| `player_media.py` | player photographs: committed assets, disk cache, live lookup |
| `theme.py` | palette, stylesheet, cards, Plotly defaults |
| `static/fonts/` | the Inter typeface (SIL Open Font Licence), served by Streamlit so the dashboard looks the same offline |
| `assets/players/` | 16 committed photographs, one per player id, with sources in `README.md` |
| `requirements.txt` | pinned `pip install -r frontend/requirements.txt` |

`app.py` resolves the data folder from its own location, so it works both as
`streamlit run frontend/app.py` and from inside `frontend/`.

## Design notes

- **Dark editorial theme.** One accent (teal) for the model, semantic colours
  only for the verdicts: green undervalued, amber overvalued, slate fairly
  valued. Colour never carries meaning alone — every colour is paired with a
  label.
- **The buffer is visible, not just described.** The profile page draws the
  no-call band around the estimate, so the ±8% tolerance (from `thresholds.json`) that decides the
  verdict is something you can see rather than a footnote.
- **Click-through tables.** Selecting a row in any table opens that player's
  profile; the jump is applied before the navigation radio is built, which is
  why it does not trip Streamlit's widget-state rule.
- **Player photographs.** The profile hero, the Overview strip of most valuable
  players and both sides of Compare show a face. Sixteen players ship with a
  committed image so the dashboard has pictures with no network; any other player
  is looked up once, cached in `frontend/.cache/`, and falls back to an initials
  plate rather than a broken frame. Nothing on screen depends on an image.
- **Deep links.** `?page=Compare` opens that page directly, which is also how the
  screenshots in `docs/VERIFICATION_AND_SCREENSHOTS.md` were captured.
- **No hard-coded numbers.** Filter options come from `/api/meta`, the verdict
  bands come from `ai-core/outputs/thresholds.json`, and the model-quality cards
  come from `model_comparison.csv`.
- **Filtering happens once, locally.** `/api/players` caps `limit` at 200, so the
  app loads the table in 90 requests (about 4 s, cached for 5 minutes) and then
  filters, sorts and pages in pandas. `/api/health` and `/api/meta` are the other
  two routes it uses.

## Not included

The live "score a new player" form (`POST /api/predict`) is deliberately absent:
the model needs all 40 features, and a form that silently filled the rest with
zeros would produce a confident but meaningless number. The prepared table
already covers every player in the dataset.
