# Reference values (the "now" side of the comparison)

The dataset's recorded market values are a snapshot. This folder holds a small,
separately collected set of **current** values, so the report can say how much
that snapshot has aged and whether the evaluation labels would change today.

## Files

| File | What it is |
| --- | --- |
| `players_to_check.csv` | The players we want current values for: `player_id`, `name`, `full_name`, `dataset_value_eur`. Edit this list freely. |
| `raw/apify_players.json` | Untouched result of the Apify scrape, with the fetch date. |
| `current_values.csv` | Tidy table built from the raw result: euros, club, source URL, match score. |

## Option A: copy the values by hand (footballtransfers.com)

Some value sites block scripts. `footballtransfers.com` returns **403 Forbidden** to
any automated request, so its numbers cannot be fetched by this project. In that case use
the fillable sheet:

```bash
cd ai-core
python ai/build_reference_values.py --template   # writes current_values.csv, empty values
```

Open `current_values.csv`, and for each row paste the current value from the site into
`current_value_eur` **in euros** (for example `25000000`), then fill `source_url` with the
page you read it from and `checked_on` with the date. Leave a row empty if you cannot find
the player; the comparison skips it and says so.

Then:

```bash
python ai/compare_then_now.py
```

Twenty to thirty filled rows is enough for the report, and it takes a few minutes in a
browser. Writing down the source URL and the date is what makes the comparison citable.

A third option, if neither of the above suits you: the CIES Football Observatory publishes
free weekly transfer-value estimates that are designed to be cited in academic work
(https://football-observatory.com). They are a different valuation method from
Transfermarkt, so label whichever source you use.

## Option B: fetch them automatically

The values come from Transfermarkt through a paid Apify Actor
(`data_xplorer/transfermarkt-api-scraper`, about $0.75 per 1,000 results, so
25 players is well under one cent). Nothing is scraped by this project directly,
and no credentials are stored in the repository.

```bash
pip install apify-client
export APIFY_API_TOKEN=...            # Apify Console -> Settings -> Integrations

cd ai-core
python ai/fetch_current_values.py     # calls the Actor, saves the raw JSON
python ai/build_reference_values.py   # parses it into current_values.csv
python ai/compare_then_now.py         # writes outputs/then_now_comparison.csv
```

Note that this option overwrites `current_values.csv`, so do not mix it with hand-filled
rows unless you keep a copy.

On Windows PowerShell use `$env:APIFY_API_TOKEN="..."` for the current session.

## Choosing the players

A sample is enough. Something in the range of 20 to 40 players is defensible for
a university report and keeps the fetch cheap. A useful spread:

- the most valuable players, where absolute drift is largest
- players across all four position groups
- a few players with no recorded value, to show the "No recorded value" path
- players whose dataset value looks unusual, to test the labels

## What the comparison is not

It does not turn the project into a live valuation system. It is a validation
step: it shows that the model's estimates sit close to the snapshot, and that the
snapshot itself has moved since it was recorded. That distinction is the whole
point of the buffer strategy in `MARKET_VALUE_LIMITATION_AND_STRATEGY.md`.
