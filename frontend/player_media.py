"""Player photographs for the dashboard, resolved once and cached on disk.

Resolution order for one player:

1. a committed image in ``frontend/assets/players/`` (works with no network),
2. a disk cache in ``frontend/.cache/photos/`` (filled the first time a page needs it),
3. Wikipedia's article summary for a known article title,
4. TheSportsDB's exact-name search,
5. nothing — the caller draws an initials plate instead.

Nothing here is required for a page to render, the network is only touched when an
image is genuinely missing, and every failed attempt is remembered so an offline
demo stays fast instead of waiting on timeouts.

Names in a 2019 FIFA dump are abbreviated ("L. Messi", "De Gea", "Neymar Jr"), so
``ALIASES`` maps the handful of short names that cannot be derived to the exact
Wikipedia article. Anything else is resolved from the full name, and the returned
article title is checked against the surname and first initial before its picture
is used — that check is what stops "H. Kane" becoming Todd Kane.

Refresh the committed set (the most valuable players in the table):

    .venv/Scripts/python frontend/player_media.py [count]

Photographs remain the property of their authors; each file's source article and the
resolved name are written to ``frontend/assets/players/credits.json``.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if (HERE.parent / "ai-core").exists() else HERE
ASSETS = HERE / "assets" / "players"
CACHE = HERE / ".cache"
PHOTOS = CACHE / "photos"
INDEX_FILE = CACHE / "lookups.json"
CREDITS_FILE = ASSETS / "credits.json"

WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
SPORTSDB_SEARCH = "https://www.thesportsdb.com/api/v1/json/{key}/searchplayers.php?p={query}"
SPORTSDB_KEY = os.environ.get("SPORTSDB_KEY", "123")
TIMEOUT = 6
MAX_SIZE = (360, 480)
SUFFIXES = (".jpg", ".png")
USER_AGENT = {"User-Agent": "Footstat304-dashboard/1.0 (university coursework)"}

# Dataset short name -> exact Wikipedia article. Only names that cannot be derived
# from the full name need an entry; all of these are players people recognise.
ALIASES = {
    "L. Messi": "Lionel Messi",
    "Cristiano Ronaldo": "Cristiano Ronaldo",
    "K. Mbappé": "Kylian Mbappé",
    "M. Salah": "Mohamed Salah",
    "H. Kane": "Harry Kane",
    "K. De Bruyne": "Kevin De Bruyne",
    "E. Hazard": "Eden Hazard",
    "R. Lewandowski": "Robert Lewandowski",
    "T. Kroos": "Toni Kroos",
    "P. Pogba": "Paul Pogba",
    "P. Dybala": "Paulo Dybala",
    "A. Griezmann": "Antoine Griezmann",
    "C. Eriksen": "Christian Eriksen",
    "Neymar Jr": "Neymar",
    "De Gea": "David de Gea",
    "L. Suárez": "Luis Suárez",
    "S. Agüero": "Sergio Agüero",
    "V. van Dijk": "Virgil van Dijk",
    "S. Mané": "Sadio Mané",
    "Alisson": "Alisson Becker",
}

# After two failed requests the module stops trying for the rest of the process,
# so an offline machine renders instantly instead of hitting a timeout per player.
_failures = 0


# ------------------------------------------------------------------ name handling


def _plain(text) -> str:
    """Strip accents so 'Mbappé' and 'Mbappe' compare equal."""
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _key(name, full_name=None) -> str:
    return _plain(f"{name or ''}|{full_name or ''}").strip().lower()


def _words(text) -> list[str]:
    return [word for word in re.split(r"[\s]+", _plain(text).strip()) if word]


def _surname_and_letter(name, full_name=None) -> tuple[str, str]:
    """('L. Messi', ...) -> ('Messi', 'L').

    The short name wins because it is the dataset's own label; the full name is only
    a fallback. 'Lionel Andrés Messi Cuccittini' would otherwise yield 'Cuccittini',
    which no article title ends with.
    """
    short = _words(name)
    if len(short) >= 2:
        return short[-1], short[0].rstrip(".")[:1].upper()
    full = _words(full_name)
    if len(full) >= 2:
        return full[-1], full[0][:1].upper()
    return ((short or full or [""])[0]), ""


def initials(name) -> str:
    """'L. Messi' -> 'LM' — used when no photograph is available."""
    words = [word for word in re.split(r"\s+", _plain(name or "?").replace(".", " ").strip()) if word]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[-1][0]).upper()


def _matches(title, surname: str, letter: str) -> bool:
    """Does this article title plausibly name the player we asked for?"""
    words = _words(title)
    if not words or not surname:
        return False
    if words[-1].lower() != surname.lower():
        return False
    return not letter or words[0][:1].upper() == letter


# ------------------------------------------------------------------------ lookups


def _index() -> dict:
    if not INDEX_FILE.exists():
        return {}
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_index(index: dict) -> None:
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        INDEX_FILE.write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _get_json(url: str):
    request = urllib.request.Request(url, headers=USER_AGENT)
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def _wikipedia(title: str, surname: str, letter: str, trusted: bool = False) -> dict | None:
    """The article's lead image, if the article really is this player."""
    payload = _get_json(WIKI_SUMMARY.format(title=urllib.parse.quote(title.replace(" ", "_"))))
    if payload.get("type") == "disambiguation":
        return None
    actual = payload.get("title") or ""
    same_article = _plain(actual).lower() == _plain(title).lower()
    if not (_matches(actual, surname, letter) or (trusted and same_article)):
        return None
    image = payload.get("thumbnail") or payload.get("originalimage") or {}
    url = image.get("source")
    if not url:
        return None
    return {
        "player": payload.get("title") or title,
        "team": "",
        "url": url,
        "source": "wikipedia",
        "article": payload.get("content_urls", {}).get("desktop", {}).get("page", ""),
    }


def _sportsdb(query: str, surname: str, letter: str) -> dict | None:
    payload = _get_json(
        SPORTSDB_SEARCH.format(key=SPORTSDB_KEY, query=urllib.parse.quote(query))
    )
    best, best_score = None, 0
    for hit in (payload or {}).get("player") or []:
        name = hit.get("strPlayer") or ""
        if not _matches(name, surname, letter):
            continue
        words = _words(name)
        score = 5 + (2 if words[-1].lower() == surname.lower() else 0)
        if score > best_score:
            best, best_score = hit, score
    if best is None:
        return None
    return {
        "player": best.get("strPlayer") or "",
        "team": best.get("strTeam") or "",
        "url": best.get("strCutout") or best.get("strThumb") or "",
        "source": "thesportsdb",
        "article": "",
    }


def resolve(name, full_name=None) -> dict | None:
    """Find one photograph for this player, remembering the answer on disk."""
    global _failures
    cache_key = _key(name, full_name)
    index = _index()
    if cache_key in index:
        return index[cache_key] or None
    if _failures >= 2:
        return None

    surname, letter = _surname_and_letter(name, full_name)
    alias = ALIASES.get(str(name or "").strip())
    record = None

    titles = [alias] if alias else []
    for candidate in (full_name, name):
        text = str(candidate or "").strip()
        if text and not re.match(r"^[A-Z]\.\s", text) and text not in titles:
            titles.append(text)
    for title in titles:
        try:
            record = _wikipedia(title, surname, letter, trusted=bool(alias) and title == alias)
        except Exception:  # 404, offline, rate limit: try the next title, remember it
            _failures += 1
            record = None
        if record:
            break
        if _failures >= 2:
            break

    if record is None and _failures < 2:
        query = alias or " ".join(_words(full_name)[:1] + _words(full_name)[-1:]) or surname
        try:
            record = _sportsdb(query, surname, letter)
        except Exception:
            _failures += 1
            record = None

    # A miss is not a failure: only network errors count towards giving up.
    index[cache_key] = record
    _save_index(index)
    return record


# ------------------------------------------------------------------------- images


def _store(raw: bytes, destination: Path) -> bool:
    """Decode, downscale to card size and write. False if it is not an image."""
    try:
        from PIL import Image
    except ImportError:
        return False
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception:
        return False
    image = image.convert("RGBA" if image.mode in ("P", "LA", "RGBA") else "RGB")
    image.thumbnail(MAX_SIZE)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if image.mode == "RGBA":
            image.save(destination.with_suffix(".png"), optimize=True)
        else:
            image.save(destination.with_suffix(".jpg"), "JPEG", quality=88, optimize=True)
    except OSError:
        return False
    return True


def _existing(folder: Path, player_id: int) -> Path | None:
    for suffix in SUFFIXES:
        path = folder / f"{int(player_id)}{suffix}"
        if path.exists():
            return path
    return None


def photo_path(player_id, name=None, full_name=None, allow_network: bool = True) -> Path | None:
    """The best available picture for this player, or None."""
    for folder in (ASSETS, PHOTOS):
        found = _existing(folder, player_id)
        if found is not None:
            return found
    if not allow_network:
        return None

    record = resolve(name, full_name)
    if not record or not record.get("url"):
        return None
    try:
        request = urllib.request.Request(record["url"], headers=USER_AGENT)
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            raw = response.read()
    except Exception:
        return None
    if not _store(raw, PHOTOS / f"{int(player_id)}.png"):
        return None
    return _existing(PHOTOS, player_id)


def photo_data_uri(player_id, name=None, full_name=None, allow_network: bool = True) -> str:
    """The picture as a data URI, for use inside the HTML hero card."""
    path = photo_path(player_id, name, full_name, allow_network)
    if path is None:
        return ""
    mime = "png" if path.suffix == ".png" else "jpeg"
    return f"data:image/{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


# --------------------------------------------------------------------------- seed


def seed(count: int = 16) -> None:
    """Copy photographs of the most valuable players into the committed assets."""
    import csv

    predictions = ROOT / "ai-core" / "outputs" / "player_predictions.csv"
    clean = ROOT / "ai-core" / "data" / "processed" / "players_clean.csv"
    with open(predictions, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    full_names: dict[str, str] = {}
    if clean.exists():
        with open(clean, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                full_names[row["player_id"]] = row.get("full_name") or ""

    valued = [row for row in rows if (row.get("actual_value_eur") or "").strip()]
    valued.sort(key=lambda row: float(row["actual_value_eur"]), reverse=True)

    credits = {}
    if CREDITS_FILE.exists():
        try:
            credits = json.loads(CREDITS_FILE.read_text(encoding="utf-8"))
        except ValueError:
            credits = {}

    ASSETS.mkdir(parents=True, exist_ok=True)
    for row in valued[:count]:
        pid = int(row["player_id"])
        full_name = full_names.get(row["player_id"], "")
        path = photo_path(pid, row["name"], full_name)
        if path is not None and path.parent == PHOTOS:
            target = ASSETS / path.name
            target.write_bytes(path.read_bytes())
            path.unlink()
            path = target
        record = resolve(row["name"], full_name) or {}
        credits[str(pid)] = {
            "name": row["name"],
            "full_name": full_name,
            "resolved": record.get("player", ""),
            "team": record.get("team", ""),
            "source": record.get("source", ""),
            "article": record.get("article", ""),
            "file": path.name if path is not None else "",
        }
        status = path.name if path is not None else "MISSING"
        print(f"{pid:>6}  {row['name']:<20} {status:<10} {record.get('player', '')}")

    CREDITS_FILE.write_text(json.dumps(credits, indent=1, ensure_ascii=False), encoding="utf-8")
    saved = sum(1 for item in credits.values() if item.get("file"))
    print(f"\n{saved} photographs committed in {ASSETS}")


if __name__ == "__main__":
    import sys

    seed(int(sys.argv[1]) if len(sys.argv) > 1 else 16)
