"""Turn the raw Apify result into a tidy reference table of current values.

Reads ``data/reference/raw/apify_players.json`` (written by
``fetch_current_values.py``) and writes ``data/reference/current_values.csv``,
one row per requested player, keeping the dataset's ``player_id`` so the table can
be joined to ``outputs/player_predictions.csv`` without name guessing.

Only standard library, so this runs on a bare Python.

Usage (from ai-core/)
---------------------
    python ai/build_reference_values.py
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "data" / "reference"
RAW_IN = REFERENCE / "raw" / "apify_players.json"
PLAYERS_FILE = REFERENCE / "players_to_check.csv"
OUT = REFERENCE / "current_values.csv"

MATCH_FLOOR = 0.55  # below this we do not trust the match

COLUMNS = [
    "player_id",
    "dataset_name",
    "tm_name",
    "match_score",
    "current_value_eur",
    "current_value_raw",
    "club",
    "source_url",
    "checked_on",
]


def parse_value(text) -> float | None:
    """Turn a Transfermarkt value string into euros.

    Handles the formats the Actor returns: "28.00M€", "€120.00m", "€1.20bn",
    "€950k", "€500,000" and the occasional dash for an unvalued player.
    """
    if text is None or isinstance(text, (int, float)):
        return None if text is None else float(text)
    cleaned = str(text).replace("\u20ac", "").replace("\u00a0", " ").strip()
    if not cleaned or cleaned in {"-", "--", "\u2013", "N/A", "?"}:
        return None

    cleaned = cleaned.replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)\s*(bn|m|k)?", cleaned, re.IGNORECASE)
    if not match:
        return None
    amount = float(match.group(1))
    unit = (match.group(2) or "").lower()
    scale = {"bn": 1_000_000_000, "m": 1_000_000, "k": 1_000}.get(unit, 1)
    return round(amount * scale, 2)


def normalise(name: str) -> str:
    """Lowercase, strip accents, drop punctuation, for comparison only."""
    import unicodedata

    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z ]", " ", text.lower()).strip()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalise(a), normalise(b)).ratio()


def best_match(requested_name: str, results):
    """The result whose player name looks most like the name we asked for."""
    scored = []
    for item in results:
        candidate = item.get("playerName") or item.get("name") or ""
        if candidate:
            scored.append((similarity(requested_name, candidate), candidate, item))
    if not scored:
        return None
    return max(scored, key=lambda entry: entry[0])


def write_template(players_file: Path, out: Path) -> None:
    """Write an empty sheet to fill in by hand.

    Use this when the values are copied from a site that blocks automated access
    (footballtransfers.com returns 403 to scripts). Fill the current_value_eur
    column, then run compare_then_now.py against this file.
    """
    with open(players_file, newline="", encoding="utf-8") as handle:
        wanted = list(csv.DictReader(handle))

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for player in wanted:
            writer.writerow(
                {
                    "player_id": player.get("player_id", ""),
                    "dataset_name": player.get("name", ""),
                    "tm_name": "",
                    "match_score": "manual",
                    "current_value_eur": "",
                    "current_value_raw": "",
                    "club": "",
                    "source_url": "",
                    "checked_on": "",
                }
            )

    print(f"Fillable sheet written: {out}")
    print(f"Rows to fill: {len(wanted)}")
    print("Enter current_value_eur in euros (e.g. 25000000), then set source_url and checked_on.")
    print(f"Next: python ai/compare_then_now.py --reference {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=RAW_IN)
    parser.add_argument("--players-file", type=Path, default=PLAYERS_FILE)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument(
        "--template",
        action="store_true",
        help="write an empty sheet to fill in by hand instead of parsing a scrape",
    )
    args = parser.parse_args()

    if args.template:
        write_template(args.players_file, args.out)
        return

    if not args.raw.exists():
        raise SystemExit(
            f"No raw result at {args.raw}. Run python ai/fetch_current_values.py first."
        )

    payload = json.loads(args.raw.read_text(encoding="utf-8"))
    results = payload.get("results", [])
    checked_on = payload.get("fetched_on") or date.today().isoformat()

    with open(args.players_file, newline="", encoding="utf-8") as handle:
        wanted = list(csv.DictReader(handle))

    rows = []
    unmatched = []
    for player in wanted:
        asked = (player.get("full_name") or player.get("name") or "").strip()
        match = best_match(asked, results)
        if match is None or match[0] < MATCH_FLOOR:
            unmatched.append((player.get("player_id"), player.get("name")))
            continue
        score, tm_name, item = match
        raw_value = item.get("marketValue")
        club = item.get("currentClub") or ""
        rows.append(
            {
                "player_id": player.get("player_id", ""),
                "dataset_name": player.get("name", ""),
                "tm_name": tm_name,
                "match_score": round(score, 3),
                "current_value_eur": parse_value(raw_value),
                "current_value_raw": raw_value,
                "club": club,
                "source_url": item.get("profileUrl") or item.get("url") or "",
                "checked_on": checked_on,
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    valued = [r for r in rows if r["current_value_eur"]]
    print(f"Requested      : {len(wanted)}")
    print(f"Matched        : {len(rows)} (with a value: {len(valued)})")
    print(f"Weak matches   : {len(unmatched)}")
    for pid, name in unmatched[:10]:
        print(f"  - player_id={pid} {name}: no confident match")
    print(f"Saved          : {args.out.relative_to(ROOT)}")
    print("\nNext: python ai/compare_then_now.py")


if __name__ == "__main__":
    main()
