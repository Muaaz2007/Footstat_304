"""Fetch current market values from Transfermarkt through an Apify Actor.

The dataset's recorded values are a snapshot, not a live price. To check how much
those values have moved since ("then" vs "now"), we collect current values for a
small set of players we already have in the dataset.

This script does not scrape anything itself. It calls the Apify Actor
``data_xplorer/transfermarkt-api-scraper``, which is a paid service, so it runs
only when you ask it to and only for the players in your list.

Setup
-----
    pip install apify-client
    export APIFY_API_TOKEN=...        # Windows: setx APIFY_API_TOKEN "..."
                                      # Apify Console -> Settings -> Integrations

The token is read from the environment on purpose: never paste it into a file in
this repository. The script prints how many players it is about to fetch before
it spends anything, and stops there unless the list looks right.

Cost
----
The Actor charges about $0.75 per 1,000 results, so 25 players cost well under one
cent on top of your Apify plan. Check the current price on the Actor page before
the first run:

    https://apify.com/data_xplorer/transfermarkt-api-scraper

Usage (from ai-core/)
---------------------
    python ai/fetch_current_values.py
    python ai/fetch_current_values.py --limit 10
    python ai/fetch_current_values.py --players-file data/reference/players_to_check.csv

Then turn the raw result into the reference table:

    python ai/build_reference_values.py
    python ai/compare_then_now.py
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "data" / "reference"
PLAYERS_FILE = REFERENCE / "players_to_check.csv"
RAW_OUT = REFERENCE / "raw" / "apify_players.json"

ACTOR = "data_xplorer/transfermarkt-api-scraper"
TOKEN_ENV = "APIFY_API_TOKEN"
MAX_ITEMS = 100  # the Actor's own limit per run


def read_players(path: Path, limit: int):
    """Names to look up, taken from our own dataset (so player_id stays known)."""
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"No players in {path}. Add rows with player_id and name.")
    return rows[:limit]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--players-file", type=Path, default=PLAYERS_FILE)
    parser.add_argument("--limit", type=int, default=MAX_ITEMS)
    parser.add_argument("--out", type=Path, default=RAW_OUT)
    parser.add_argument(
        "--with-history",
        action="store_true",
        help="also fetch each player's market value timeline (slower, more requests)",
    )
    args = parser.parse_args()

    token = os.environ.get(TOKEN_ENV)
    if not token:
        raise SystemExit(
            f"Set {TOKEN_ENV} first: this Actor is a paid service and needs your "
            "Apify token.\nCreate one at https://console.apify.com/settings/integrations "
            "and export it; do not put it in a project file."
        )

    try:
        from apify_client import ApifyClient
    except ImportError:
        raise SystemExit("apify-client is not installed. Run: pip install apify-client")

    players = read_players(args.players_file, min(args.limit, MAX_ITEMS))
    items = [(row.get("full_name") or row["name"]).strip() for row in players]

    print(f"Player list : {args.players_file}")
    print(f"Players     : {len(items)}")
    print(f"Estimate    : about ${len(items) * 0.00075:.4f} of Actor usage "
          "(plus your Apify plan)")
    print(f"History     : {'yes' if args.with_history else 'no'}")
    print(f"Run date    : {date.today().isoformat()}")
    for name in items[:5]:
        print(f"  - {name}")
    if len(items) > 5:
        print(f"  ... and {len(items) - 5} more")

    run_input = {
        "scrapeType": "players",
        "items": items,
        "playersWithoutStatistics": True,
        "playerMarketValueHistory": bool(args.with_history),
        "playerAgentDetails": False,
        "proxyConfig": {"useApifyProxy": True},
    }

    client = ApifyClient(token)
    print("\nStarting the Actor...")
    run = client.actor(ACTOR).call(run_input=run_input)
    dataset_id = run.default_dataset_id
    print(f"Dataset: https://console.apify.com/storage/datasets/{dataset_id}")

    results = list(client.dataset(dataset_id).iterate_items())

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "fetched_on": date.today().isoformat(),
                "actor": ACTOR,
                "requested": items,
                "results": results,
            },
            handle,
            indent=2,
            ensure_ascii=False,
        )

    print(f"Saved {len(results)} result(s) to {args.out.relative_to(ROOT)}")
    print("Next: python ai/build_reference_values.py")


if __name__ == "__main__":
    main()
