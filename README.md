# Footstat 304

A football player evaluation system made of three layers: a backend, an AI model, and a Streamlit dashboard.

## What it does

The backend reads the dataset of 17,954 players and serves one value estimate per player. The estimate comes from a model trained on each player's attributes and position. There are two ways to use it: the current prediction table, and a live endpoint that runs the model on a player outside the table.

The dashboard reads that estimate and shows it as a table, a single-player profile, a two-player comparison, and a short explanation of how the estimate is produced.

Each player has a **recorded value** (from the dataset) and a **model estimate** (from the player's attributes). If the gap is small enough, the player is called **fairly valued**. If the estimate is below the record, the player is labeled **overvalued**. If the estimate is above the record, the player is labeled **undervalued**. The cut-off between those labels comes from the model's own error, so small differences are treated as noise.

In the default view, around a thousand players are called potentially undervalued and around a thousand are called potentially overvalued, and most of the table is fairly valued.

## What this is not

This is an evaluation support tool. It does not give the true market value of a player. The recorded value is what the dataset says, not what the market paid, and the estimate is not a better market value either. The system is meant to help people analyse players, not to price them.

## Quick start

- Backend on port 8000, dashboard on port 8501. There is currently no one-command start, so they still take two terminals.
- Each layer has its own README: `backend/`, `ai/`, `ai-core/`, `data/`, and `frontend/`.

## Documentation

- `docs/IMPLEMENTATION_NOTES.md` - what was built and why
- `docs/RESULTS_AND_CHANGES.md` - the verified numbers and what changed
- `docs/FRONTEND_INTEGRATION_STREAMLIT.md` - the interface the dashboard was built against
- `docs/VERIFICATION_AND_SCREENSHOTS.md` - the verification run with screenshots
- `docs/ROUTE_TO_REPORT.md` - where each document maps onto a chapter in the Word pack
- `ai-core/MARKET_VALUE_LIMITATION_AND_STRATEGY.md` - the market-value limitation and the tradeoff strategy
- `ai-core/INTERFACE_FOR_DASHBOARD.md` - the dashboard interface


## Verification

The quick summary is this:

- backend tests - 39 unit tests
- ai runtime tests - 6 tests
- pytest ai-core/tests - 7 tests

All pass on the current machine on the current data and model. The AI runtime tests skip cleanly when the model bundle is absent, so a fresh clone reports skipped instead of an error.

## How the dashboard looks

The dashboard uses the same dark theme in every page. Player photos come straight from the committed assets, so they show up without a network connection. The most valuable players page shows a strip of six players with photos and values. The comparison page shows two player photos side by side and a radar of their attributes.

## What still needs to be done

The three layers are in place end to end, so the remaining work is finishing work:

- keep the report and the documentation consistent with what the system delivers
- decide where the live single-player prediction page belongs
- keep the description of what the system delivers up to date
