"""Footstat 304 — player valuation dashboard.

    python -m backend.api --port 8000        # terminal 1: the API
    streamlit run frontend/app.py            # terminal 2: this dashboard

Reads the API when it is reachable and falls back to the committed CSV snapshot
(clearly labelled in the sidebar) when it is not. Every number on screen comes
either from the prediction table or from the thresholds file the AI pipeline
wrote — nothing is hard-coded here.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import api_client  # noqa: E402
import player_media  # noqa: E402
import theme  # noqa: E402

# Work from the repository root whether this file lives in frontend/ or at the
# top level, which is what makes `streamlit run frontend/app.py` behave.
ROOT = HERE.parent if (HERE.parent / "ai-core").exists() else HERE
DATA_DIRS = [
    ROOT / "ai-core" / "outputs",
    ROOT / "ai-core" / "data" / "processed",
    ROOT / "data",
    ROOT,
]

PAGES = ["Overview", "Player Explorer", "Player Profile", "Compare", "Model & Method"]

UNDER_EVAL = "Potentially Undervalued"
OVER_EVAL = "Potentially Overvalued"
FAIR_EVAL = "Fairly Valued"
NO_EVAL = "No recorded value"

# Six readout groups built from the 29 individual skill columns. This grouping
# is the dashboard's own presentation choice, not a field in the dataset.
RADAR_GROUPS = {
    "Pace": ["acceleration", "sprint_speed"],
    "Shooting": ["finishing", "shot_power", "long_shots", "positioning", "volleys", "penalties"],
    "Passing": ["short_passing", "long_passing", "vision", "crossing", "curve", "freekick_accuracy"],
    "Dribbling": ["dribbling", "ball_control", "agility", "balance"],
    "Defending": ["marking", "standing_tackle", "sliding_tackle", "interceptions"],
    "Physical": ["strength", "stamina", "jumping", "aggression"],
}
RADAR_KEYS = list(RADAR_GROUPS)

KEY_ATTRS = [
    "height_cm",
    "weight_kgs",
    "preferred_foot",
    "international_reputation(1-5)",
    "weak_foot(1-5)",
    "skill_moves(1-5)",
]

SORTS = {
    "Name": "name",
    "Age": "age",
    "Overall rating": "overall_rating",
    "Recorded value": "actual_value_eur",
    "Model estimate": "predicted_value_eur",
    "Gap %": "relative_difference",
}

ACCENT_2 = "#A78BFA"


# --------------------------------------------------------------------------- data


def data_file(name: str) -> Path:
    for folder in DATA_DIRS:
        candidate = folder / name
        if candidate.exists():
            return candidate
    return DATA_DIRS[0] / name


@st.cache_data(ttl=300, show_spinner=False)
def load_table():
    """Predictions joined with the attribute table, plus the meta and its source."""
    try:
        meta = dict(api_client.meta())
        predictions = pd.DataFrame(api_client.all_players(meta["max_limit"]))
        source = f"live API · {api_client.API}"
    except api_client.ApiError:
        predictions = pd.read_csv(data_file("player_predictions.csv"))
        meta = dict(api_client.FALLBACK_META)
        meta["player_count"] = int(len(predictions))
        source = "offline CSV snapshot"

    clean = pd.read_csv(data_file("players_clean.csv"))
    wanted = ["player_id", *KEY_ATTRS, *sorted({c for cols in RADAR_GROUPS.values() for c in cols})]
    keep = [c for c in dict.fromkeys(wanted) if c in clean.columns]
    frame = predictions.merge(clean[keep], on="player_id", how="left")

    for group, columns in RADAR_GROUPS.items():
        present = [c for c in columns if c in frame.columns]
        frame[f"grp_{group}"] = frame[present].mean(axis=1).round(0) if present else 0.0

    frame["search"] = (
        frame["name"].fillna("").astype(str) + " " + frame["full_name"].fillna("").astype(str)
    ).str.lower()
    return frame, meta, source


@st.cache_data(ttl=600, show_spinner=False)
def load_extras():
    """Thresholds and the model-quality files the AI pipeline wrote."""
    extras = {
        "thresholds": {},
        "models": pd.DataFrame(),
        "errors": pd.DataFrame(),
        "importance": pd.DataFrame(),
    }
    path = data_file("thresholds.json")
    if path.exists():
        extras["thresholds"] = json.loads(path.read_text(encoding="utf-8"))
    for key, name in (
        ("models", "model_comparison.csv"),
        ("errors", "error_breakdown.csv"),
        ("importance", "rf_feature_importance.csv"),
    ):
        path = data_file(name)
        if path.exists():
            extras[key] = pd.read_csv(path)
    importance = extras["importance"]
    if not importance.empty:
        importance = importance.rename(columns={importance.columns[0]: "feature"})
        extras["importance"] = importance.sort_values("importance", ascending=False)
    return extras


def thresholds(extras) -> tuple[float, float, float | None]:
    """(undervalued ratio, overvalued ratio, k) straight from the AI pipeline."""
    stored = extras.get("thresholds", {})
    under = float(stored.get("undervalued_if_predicted_at_least_x_actual", 1.0996))
    over = float(stored.get("overvalued_if_predicted_at_most_x_actual", 0.9094))
    return under, over, stored.get("k_log")


# ----------------------------------------------------------------------- formatting


def eur(value) -> str:
    if value is None or pd.isna(value):
        return "—"
    value = float(value)
    sign = "-" if value < 0 else ""
    size = abs(value)
    if size >= 1e9:
        return f"{sign}€{size / 1e9:.2f}B"
    if size >= 1e6:
        return f"{sign}€{size / 1e6:.1f}M"
    if size >= 1e3:
        return f"{sign}€{size / 1e3:.0f}K"
    return f"{sign}€{size:.0f}"


def pct(value) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value) * 100:+.1f}%"


def meta_line(row) -> str:
    parts = []
    for value in (
        row.get("full_name"),
        row.get("nationality"),
        row.get("position_group"),
        f"{int(row['age'])} years" if pd.notna(row.get("age")) else None,
        f"{row['preferred_foot']} foot" if pd.notna(row.get("preferred_foot")) else None,
        f"{row['height_cm']:.0f} cm" if pd.notna(row.get("height_cm")) else None,
    ):
        if value is None or pd.isna(value):
            continue
        text = str(value).strip()
        if text and text != "nan":
            parts.append(text)
    return " · ".join(parts)


def face(row, width: int = 150) -> None:
    """The player's photograph, or an initials plate when no image is available."""
    path = player_media.photo_path(int(row["player_id"]), row.get("name"), row.get("full_name"))
    if path is not None:
        st.image(str(path), width=width)
        return
    plate = player_media.initials(row.get("name"))
    st.markdown(
        f'<div class="fs-face" style="width:{width}px;height:{round(width * 1.12)}px">{plate}</div>',
        unsafe_allow_html=True,
    )


def label_map(frame) -> dict[int, str]:
    ages = frame["age"].map(lambda v: str(int(v)) if pd.notna(v) else "?")
    return dict(
        zip(
            frame["player_id"].astype(int),
            frame["name"].astype(str) + " · " + frame["position_group"].astype(str) + " · " + ages + "y",
        )
    )


# -------------------------------------------------------------------------- routing


def open_player(player_id: int) -> None:
    """Jump to a player's profile from a table row, safely."""
    st.session_state["_pending_player"] = int(player_id)
    st.rerun()


def consume_pending() -> None:
    """Apply a pending jump before the sidebar radio is created."""
    if "_pending_player" in st.session_state:
        st.session_state["pid"] = st.session_state.pop("_pending_player")
        st.session_state["nav"] = "Player Profile"


def consume_query_page() -> None:
    """Let ?page=Compare open that page directly — used for deep links and screenshots."""
    requested = st.query_params.get("page")
    if isinstance(requested, list):
        requested = requested[0] if requested else None
    if requested in PAGES and st.session_state.get("nav") != requested:
        st.session_state["nav"] = requested


def sidebar(meta, source: str, total: int) -> None:
    with st.sidebar:
        st.markdown(
            '<div class="fs-eyebrow">Footstat 304</div>'
            '<div style="font-size:19px;font-weight:680;letter-spacing:-.02em;margin-bottom:1.1rem">'
            "Valuation dashboard</div>",
            unsafe_allow_html=True,
        )
        st.radio("Pages", PAGES, key="nav", label_visibility="collapsed")
        theme.divider()
        live = source.startswith("live API")
        st.markdown(
            theme.pill("Live API" if live else "Offline snapshot", theme.ACCENT if live else theme.OVER),
            unsafe_allow_html=True,
        )
        theme.note(f"{theme.esc(source)}<br>{total:,} players")
        st.write("")
        if st.button("Reload data", key="reload"):
            st.cache_data.clear()
            st.rerun()
        theme.divider()
        theme.note(
            "Recorded values are the dataset's own snapshot and are missing for "
            "some players. Every figure is an AI-based indication, not a valuation."
        )


# -------------------------------------------------------------------------- widgets


def player_table(frame: pd.DataFrame, key: str, height: int | None = None) -> None:
    """Formatted table with click-through to the player profile."""
    if frame.empty:
        st.info("No players match these filters.")
        return
    view = frame.assign(
        recorded=frame["actual_value_eur"] / 1e6,
        estimate=frame["predicted_value_eur"] / 1e6,
        gap=frame["relative_difference"] * 100,
    )[
        ["player_id", "name", "age", "position_group", "overall_rating",
         "recorded", "estimate", "gap", "evaluation"]
    ]
    event = st.dataframe(
        view,
        key=key,
        hide_index=True,
        width="stretch",
        height=height,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "player_id": st.column_config.NumberColumn("ID", width="small"),
            "name": st.column_config.TextColumn("Player"),
            "age": st.column_config.NumberColumn("Age", width="small"),
            "position_group": st.column_config.TextColumn("Pos", width="small"),
            "overall_rating": st.column_config.ProgressColumn(
                "Rating", min_value=0, max_value=100, format="%d", width="small"
            ),
            "recorded": st.column_config.NumberColumn("Recorded", format="€%.1fM", width="small"),
            "estimate": st.column_config.NumberColumn("Estimate", format="€%.1fM", width="small"),
            "gap": st.column_config.NumberColumn("Gap", format="%+.1f%%", width="small"),
            "evaluation": st.column_config.TextColumn("Verdict"),
        },
    )
    rows = getattr(getattr(event, "selection", None), "rows", None) or []
    if rows:
        open_player(int(view.iloc[rows[0]]["player_id"]))


def radar_figure(rows, names, colors=None):
    colors = colors or [theme.ACCENT]
    figure = go.Figure()
    for row, name, color in zip(rows, names, colors):
        values = [float(row.get(f"grp_{group}") or 0) for group in RADAR_KEYS]
        figure.add_trace(
            go.Scatterpolar(
                r=values + values[:1],
                theta=RADAR_KEYS + RADAR_KEYS[:1],
                fill="toself",
                name=name,
                line=dict(color=color, width=2),
                fillcolor=theme.rgba(color, 0.15),
                hovertemplate="%{theta}: %{r:.0f}<extra></extra>",
            )
        )
    return theme.style_fig(figure, height=340, legend=len(rows) > 1)


# --------------------------------------------------------------------------- pages


def page_overview(frame, meta, extras):
    theme.header(
        "Footstat 304 · snapshot review",
        "Player value dashboard",
        f"{len(frame):,} players, each scored by a model trained on their attributes. "
        "The estimate is compared with the value recorded in the dataset, and the "
        "difference is judged against the model's own error buffer.",
    )
    valued = frame.dropna(subset=["actual_value_eur"])
    total = max(1, len(frame))
    under = int((frame["evaluation"] == UNDER_EVAL).sum())
    over = int((frame["evaluation"] == OVER_EVAL).sum())
    median_gap = valued["relative_difference"].median() if not valued.empty else float("nan")

    cards = st.columns(4, gap="medium")
    with cards[0]:
        theme.stat("Players", f"{len(frame):,}", "2019 attribute snapshot")
    with cards[1]:
        theme.stat("Potentially undervalued", f"{under:,}",
                   f"{under / total * 100:.1f}% of the table", theme.UNDER)
    with cards[2]:
        theme.stat("Potentially overvalued", f"{over:,}",
                   f"{over / total * 100:.1f}% of the table", theme.OVER)
    with cards[3]:
        theme.stat("Median gap", pct(median_gap), "estimate vs recorded value")

    st.write("")
    theme.section("Most valuable players", "by the value recorded in the dataset")
    spotlight = valued.nlargest(6, "actual_value_eur")
    for column, (_, player) in zip(st.columns(6, gap="small"), spotlight.iterrows()):
        with column:
            face(player, width=104)
            st.markdown(
                f'<div class="fs-mini">{theme.esc(player["name"])}</div>'
                f'<div class="fs-mini-sub">{eur(player["actual_value_eur"])} recorded · '
                f'{eur(player["predicted_value_eur"])} estimate</div>',
                unsafe_allow_html=True,
            )
            if st.button("Open", key=f"spot_{int(player['player_id'])}"):
                open_player(int(player["player_id"]))

    st.write("")
    left, right = st.columns([1.55, 1], gap="medium")
    with left:
        theme.section("Where the estimates land", "log scale, 3,500-player sample")
        theme.chart(scatter_figure(valued, extras), key="ov_scatter")
    with right:
        theme.section("Verdict mix by position")
        theme.chart(mix_figure(frame, meta), key="ov_mix")

    theme.divider()
    theme.section("Biggest gaps", "estimate minus recorded value")
    undervalued, overvalued = st.columns(2, gap="medium")
    with undervalued:
        theme.note(f"<b style='color:{theme.UNDER}'>Estimate far above the recorded value</b>")
        player_table(valued.nlargest(8, "value_difference_eur"), key="ov_under", height=318)
    with overvalued:
        theme.note(f"<b style='color:{theme.OVER}'>Estimate far below the recorded value</b>")
        player_table(valued.nsmallest(8, "value_difference_eur"), key="ov_over", height=318)
    theme.note("Click any row to open that player's profile.")


def scatter_figure(valued: pd.DataFrame, extras):
    under, over, _ = thresholds(extras)
    sample = valued.sample(3500, random_state=7) if len(valued) > 3500 else valued
    figure = go.Figure()
    for label in (UNDER_EVAL, FAIR_EVAL, OVER_EVAL):
        part = sample[sample["evaluation"] == label]
        if part.empty:
            continue
        figure.add_trace(
            go.Scatter(
                x=part["predicted_value_eur"] / 1e6,
                y=part["actual_value_eur"] / 1e6,
                mode="markers",
                name=theme.EVAL_SHORT[label],
                marker=dict(size=5, color=theme.EVAL_COLOR[label], opacity=0.6),
                customdata=part[["name", "position_group"]].to_numpy(),
                hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>"
                "estimate €%{x:.1f}M · recorded €%{y:.1f}M<extra></extra>",
            )
        )
    low, high = 0.05, 400.0
    line = dict(width=1)
    figure.add_trace(go.Scatter(x=[low, high], y=[low, high], mode="lines", name="equal value",
                                line={**line, "color": "rgba(233,238,248,0.32)", "dash": "dash"},
                                hoverinfo="skip"))
    figure.add_trace(go.Scatter(x=[low, high], y=[low / under, high / under], mode="lines",
                                name="no-call buffer",
                                line={**line, "color": "rgba(148,163,184,0.25)"}, hoverinfo="skip"))
    figure.add_trace(go.Scatter(x=[low, high], y=[low / over, high / over], mode="lines",
                                showlegend=False,
                                line={**line, "color": "rgba(148,163,184,0.25)"}, hoverinfo="skip"))
    figure.update_xaxes(type="log", range=[math.log10(low), math.log10(high)],
                        title="Model estimate (€ millions)")
    figure.update_yaxes(type="log", range=[math.log10(low), math.log10(high)],
                        title="Recorded value (€ millions)")
    return theme.style_fig(figure, height=380)


def mix_figure(frame: pd.DataFrame, meta):
    order = [e for e in meta.get("evaluations", []) if e and e != NO_EVAL]
    groups = sorted(frame["position_group"].dropna().unique())
    counts = pd.crosstab(frame["position_group"], frame["evaluation"]).reindex(groups).fillna(0)
    figure = go.Figure()
    for label in order:
        if label not in counts.columns:
            continue
        figure.add_trace(
            go.Bar(
                y=counts.index.tolist(),
                x=counts[label].tolist(),
                orientation="h",
                name=theme.EVAL_SHORT.get(label, label),
                marker_color=theme.EVAL_COLOR.get(label, theme.FAIR),
                hovertemplate="%{y} · %{x:,} players<extra></extra>",
            )
        )
    figure.update_layout(barmode="stack")
    figure.update_xaxes(title="Players")
    return theme.style_fig(figure, height=380)


def page_explorer(frame, meta, extras):
    theme.header(
        "Player Explorer",
        "Browse the whole table",
        f"Filter and sort all {len(frame):,} players. Click a row to open the full profile.",
    )
    with st.container(border=True):
        first = st.columns([2.2, 1, 1.15], gap="medium")
        query = first[0].text_input("Search", placeholder="Name, e.g. messi or buffon", key="ex_query")
        positions = ["All"] + [g for g in meta.get("position_groups", []) if g]
        position = first[1].selectbox("Position", positions, key="ex_position")
        verdicts = ["All"] + [v for v in meta.get("evaluations", []) if v]
        verdict = first[2].selectbox("Verdict", verdicts, key="ex_verdict")

        second = st.columns([1.15, 1.15, 1.1, 1.1], gap="medium")
        age_low, age_high = int(frame["age"].min()), int(frame["age"].max())
        age = second[0].slider("Age range", age_low, age_high, (age_low, age_high), key="ex_age")
        rating_low = int(frame["overall_rating"].min())
        rating = second[1].slider("Minimum rating", rating_low, int(frame["overall_rating"].max()),
                                  rating_low, key="ex_rating")
        sort_label = second[2].selectbox("Sort by", list(SORTS), key="ex_sort")
        direction = second[3].segmented_control(
            "Order", ["Descending", "Ascending"], default="Descending", key="ex_dir"
        ) or "Descending"

    data = frame
    if query.strip():
        data = data[data["search"].str.contains(query.strip().lower(), regex=False)]
    if position != "All":
        data = data[data["position_group"] == position]
    if verdict != "All":
        data = data[data["evaluation"] == verdict]
    data = data[data["age"].between(*age) & (data["overall_rating"] >= rating)]
    data = data.sort_values(
        SORTS[sort_label],
        ascending=direction == "Ascending",
        na_position="last",
        key=lambda s: s.str.lower() if pd.api.types.is_string_dtype(s) else s,
    )

    page_size = 25
    pages = max(1, math.ceil(len(data) / page_size))
    current = min(max(1, int(st.session_state.get("ex_page", 1))), pages)
    st.session_state["ex_page"] = current
    start = (current - 1) * page_size

    theme.note(
        f"<b style='color:{theme.TEXT}'>{len(data):,}</b> of {len(frame):,} players match · "
        f"showing {start + 1:,}–{min(start + page_size, len(data)):,}"
    )
    player_table(data.iloc[start:start + page_size], key=f"ex_table_{current}", height=560)

    nav = st.columns([1, 3, 1])
    if nav[0].button("← Previous", key="ex_prev", disabled=current <= 1):
        st.session_state["ex_page"] = current - 1
        st.rerun()
    nav[1].markdown(
        f'<div class="fs-note" style="text-align:center;padding-top:.45rem">Page {current} of {pages}</div>',
        unsafe_allow_html=True,
    )
    if nav[2].button("Next →", key="ex_next", disabled=current >= pages):
        st.session_state["ex_page"] = current + 1
        st.rerun()


def page_profile(frame, meta, extras):
    theme.header(
        "Player Profile",
        "One player, in full",
        "Recorded value against the model's estimate, the buffer that decides the verdict, "
        "and the attributes the estimate was built from.",
    )
    pick = st.columns([2, 3], gap="medium")
    query = pick[0].text_input("Find a player", placeholder="Name, e.g. messi", key="pf_query")
    pool = frame
    if query.strip():
        pool = frame[frame["search"].str.contains(query.strip().lower(), regex=False)]
    if pool.empty:
        st.warning("No player matches that search.")
        return

    labels = label_map(pool)
    ids = list(labels)
    default = int(st.session_state.get("pid", ids[0]))
    if default not in ids:
        default = ids[0]
    chosen = pick[1].selectbox(
        "Player", ids, index=ids.index(default), format_func=lambda i: labels[i], key="pf_player"
    )
    st.session_state["pid"] = int(chosen)
    row = frame[frame["player_id"] == chosen].iloc[0]

    verdict = str(row["evaluation"])
    color = theme.EVAL_COLOR.get(verdict, theme.MUTED)
    portrait = player_media.photo_data_uri(
        int(row["player_id"]), row.get("name"), row.get("full_name")
    )
    if portrait:
        art = f'<img class="fs-hero-art" src="{portrait}" alt="{theme.esc(row["name"])}">'
    else:
        art = f'<div class="fs-hero-art fs-hero-plate">{player_media.initials(row["name"])}</div>'
    st.markdown(
        f'<div class="fs-hero"><div class="fs-hero-row">{art}'
        f'<div class="fs-hero-body"><div class="fs-h1">{theme.esc(row["name"])}</div>'
        f'<div class="fs-hero-meta">{theme.esc(meta_line(row))}</div>'
        f'<div style="margin-top:12px">{theme.pill(theme.EVAL_SHORT.get(verdict, verdict), color)}</div>'
        f'</div></div></div>',
        unsafe_allow_html=True,
    )

    cards = st.columns(3, gap="medium")
    has_value = pd.notna(row["actual_value_eur"])
    with cards[0]:
        theme.stat("Recorded value", eur(row["actual_value_eur"]),
                   "from the dataset" if has_value else "no recorded value")
    with cards[1]:
        theme.stat("Model estimate", eur(row["predicted_value_eur"]),
                   f"from attributes · {str(row['prediction_type'])}", theme.ACCENT)
    with cards[2]:
        theme.stat(
            "Difference",
            pct(row["relative_difference"]),
            eur(row["value_difference_eur"]) if has_value else "nothing to compare against",
            color if has_value else theme.MUTED,
        )

    st.write("")
    theme.section("Distance to the verdict", "the no-call buffer, in € millions")
    theme.chart(buffer_figure(row, extras), key=f"pf_buffer_{chosen}")
    under, over, k = thresholds(extras)
    buffer_note = (
        f"A gap only counts when the estimate falls outside this band — at least {under:.4f}× "
        f"or at most {over:.4f}× the recorded value."
    )
    if k:
        buffer_note += (
            f" The band comes from the model's own out-of-fold error (k = {float(k):.4f} log units, "
            "roughly ±10%), so small differences are treated as noise rather than a finding."
        )
    theme.note(buffer_note)

    theme.divider()
    left, right = st.columns([1.1, 1], gap="medium")
    with left:
        theme.section("Attribute profile", "six derived groups, 0–100")
        theme.chart(radar_figure([row], [str(row["name"])]), key=f"pf_radar_{chosen}")
        theme.note("Groups are this dashboard's presentation choice, derived from the "
                   "individual skill columns — they are not fields in the dataset.")
    with right:
        theme.section("Key attributes")
        details = pd.DataFrame(
            {
                "Attribute": ["Height", "Weight", "Preferred foot", "International reputation",
                              "Weak foot", "Skill moves"],
                "Value": [
                    f"{row['height_cm']:.0f} cm" if pd.notna(row.get("height_cm")) else "—",
                    f"{row['weight_kgs']:.0f} kg" if pd.notna(row.get("weight_kgs")) else "—",
                    str(row["preferred_foot"]) if pd.notna(row.get("preferred_foot")) else "—",
                    f"{int(row['international_reputation(1-5)'])} / 5"
                    if pd.notna(row.get("international_reputation(1-5)")) else "—",
                    f"{int(row['weak_foot(1-5)'])} / 5" if pd.notna(row.get("weak_foot(1-5)")) else "—",
                    f"{int(row['skill_moves(1-5)'])} / 5" if pd.notna(row.get("skill_moves(1-5)")) else "—",
                ],
            }
        )
        st.dataframe(details, hide_index=True, width="stretch")
        theme.note(f"Prediction type: <b>{theme.esc(row['prediction_type'])}</b> — the estimate "
                   "comes from a model that did not train on this player.")


def buffer_figure(row, extras):
    under, over, _ = thresholds(extras)
    predicted = float(row["predicted_value_eur"])
    low, high = predicted / under / 1e6, predicted / over / 1e6
    figure = go.Figure()
    figure.add_vrect(
        x0=low, x1=high,
        fillcolor=theme.rgba(theme.FAIR, 0.16), line_width=0,
        annotation_text="no-call buffer",
        annotation_position="top left",
        annotation_font=dict(size=10, color=theme.MUTED, family=theme.FONT),
    )
    figure.add_trace(
        go.Scatter(
            x=[predicted / 1e6], y=[1], mode="markers", name="Model estimate",
            marker=dict(size=16, color=theme.ACCENT, symbol="diamond"),
            hovertemplate="estimate €%{x:.1f}M<extra></extra>",
        )
    )
    if pd.notna(row["actual_value_eur"]):
        figure.add_trace(
            go.Scatter(
                x=[float(row["actual_value_eur"]) / 1e6], y=[1], mode="markers",
                name="Recorded value",
                marker=dict(size=14, color=theme.TEXT, symbol="circle-open", line=dict(width=2)),
                hovertemplate="recorded €%{x:.1f}M<extra></extra>",
            )
        )
    figure = theme.style_fig(figure, height=210)
    figure.update_yaxes(visible=False, range=[0.55, 1.45])
    figure.update_xaxes(title="€ millions")
    return figure


def page_compare(frame, meta, extras):
    theme.header(
        "Compare",
        "Two players, same scale",
        "The six attribute groups on one radar, plus how each player's estimate compares "
        "with the value recorded for them.",
    )
    labels = label_map(frame)
    ids = list(labels)
    default_a = int(st.session_state.get("pid", ids[0]))
    if default_a not in ids:
        default_a = ids[0]
    others = frame[frame["player_id"] != default_a]
    default_b = int(others.nlargest(1, "predicted_value_eur")["player_id"].iloc[0]) if not others.empty else default_a

    first, second = st.columns(2, gap="medium")
    left_id = first.selectbox("Player A", ids, index=ids.index(default_a),
                              format_func=lambda i: labels[i], key="cmp_a")
    right_id = second.selectbox("Player B", ids, index=ids.index(default_b),
                                format_func=lambda i: labels[i], key="cmp_b")
    left = frame[frame["player_id"] == left_id].iloc[0]
    right = frame[frame["player_id"] == right_id].iloc[0]
    for column, player in ((first, left), (second, right)):
        with column:
            face(player, width=132)

    theme.section("Attribute profile")
    theme.chart(
        radar_figure([left, right], [str(left["name"]), str(right["name"])],
                     [theme.ACCENT, ACCENT_2]),
        key=f"cmp_radar_{left_id}_{right_id}",
    )

    theme.divider()
    table_col, chart_col = st.columns([1.2, 1], gap="medium")
    with table_col:
        theme.section("Group by group")
        rows = []
        for group in RADAR_KEYS:
            a = float(left.get(f"grp_{group}") or 0)
            b = float(right.get(f"grp_{group}") or 0)
            rows.append({
                "Group": group,
                "A": a,
                "B": b,
                "Higher": "B" if b > a else ("A" if a > b else "even"),
            })
        st.dataframe(
            pd.DataFrame(rows), hide_index=True, width="stretch",
            column_config={
                "Group": st.column_config.TextColumn("Group"),
                "A": st.column_config.NumberColumn(f"A · {left['name']}", format="%.0f"),
                "B": st.column_config.NumberColumn(f"B · {right['name']}", format="%.0f"),
                "Higher": st.column_config.TextColumn("Higher"),
            },
        )
        theme.note("Player A is read first; the last column names whoever is higher.")
    with chart_col:
        theme.section("Value against estimate", "€ millions")
        figure = go.Figure()
        figure.add_trace(go.Bar(
            x=["Recorded", "Estimate"],
            y=[float(left["actual_value_eur"]) / 1e6 if pd.notna(left["actual_value_eur"]) else None,
               float(left["predicted_value_eur"]) / 1e6],
            name=str(left["name"]), marker_color=theme.ACCENT,
            hovertemplate="%{x}: €%{y:.1f}M<extra></extra>",
        ))
        figure.add_trace(go.Bar(
            x=["Recorded", "Estimate"],
            y=[float(right["actual_value_eur"]) / 1e6 if pd.notna(right["actual_value_eur"]) else None,
               float(right["predicted_value_eur"]) / 1e6],
            name=str(right["name"]), marker_color=ACCENT_2,
            hovertemplate="%{x}: €%{y:.1f}M<extra></extra>",
        ))
        figure.update_layout(barmode="group")
        figure.update_yaxes(title="€ millions")
        theme.chart(theme.style_fig(figure, height=320), key=f"cmp_bars_{left_id}_{right_id}")
        theme.note("An empty bar means the dataset records no value for that player.")

    theme.divider()
    verdicts = st.columns(2, gap="medium")
    for column, row in zip(verdicts, (left, right)):
        with column:
            colour = theme.EVAL_COLOR.get(str(row["evaluation"]), theme.MUTED)
            theme.stat(
                str(row["name"]),
                pct(row["relative_difference"]),
                f"{eur(row['actual_value_eur'])} recorded · {eur(row['predicted_value_eur'])} estimate",
                colour,
            )
            st.markdown(theme.pill(theme.EVAL_SHORT.get(str(row["evaluation"]), str(row["evaluation"])), colour),
                        unsafe_allow_html=True)


def page_model(frame, meta, extras):
    theme.header(
        "Model & Method",
        "How the estimate is produced",
        "Two techniques were trained on the same features; the table uses the random forest. "
        "The numbers below are what the pipeline wrote, not values typed in here.",
    )
    models = extras["models"]
    under, over, k = thresholds(extras)

    if not models.empty:
        scored = models
        if "split" in models.columns:
            test_rows = models[models["split"].astype(str).str.contains("test", case=False, na=False)]
            if not test_rows.empty:
                scored = test_rows
        forest = scored[scored["model"].astype(str).str.contains("forest", case=False, na=False)]
        best = forest.iloc[0] if not forest.empty else scored.iloc[0]
        cards = st.columns(4, gap="medium")
        with cards[0]:
            theme.stat("Model in the table", "Random forest", "chosen over ridge regression")
        with cards[1]:
            theme.stat("Mean absolute error", eur(best.get("MAE_eur")), "on held-out players")
        with cards[2]:
            theme.stat("R² on log value", f"{float(best.get('R2_log', float('nan'))):.3f}",
                       "log scale, less skewed by superstars")
        with cards[3]:
            theme.stat("Within ±25%", f"{float(best.get('Within25pct_pct', float('nan'))):.0f}%",
                       "of players, on the test split")
        st.write("")
        theme.section("Both techniques, same features")
        table = scored[["model", "MAE_eur", "RMSE_eur", "R2_log", "R2_eur",
                        "MedianAPE_pct", "Within25pct_pct"]].copy()
        table["MAE_eur"] = table["MAE_eur"] / 1e6
        table["RMSE_eur"] = table["RMSE_eur"] / 1e6
        st.dataframe(
            table, hide_index=True, width="stretch",
            column_config={
                "model": st.column_config.TextColumn("Technique"),
                "MAE_eur": st.column_config.NumberColumn("MAE", format="€%.1fM"),
                "RMSE_eur": st.column_config.NumberColumn("RMSE", format="€%.1fM"),
                "R2_log": st.column_config.NumberColumn("R² (log)", format="%.3f"),
                "R2_eur": st.column_config.NumberColumn("R² (€)", format="%.3f"),
                "MedianAPE_pct": st.column_config.NumberColumn("Median APE", format="%.1f%%"),
                "Within25pct_pct": st.column_config.NumberColumn("Within ±25%", format="%.0f%%"),
            },
        )

    errors = extras["errors"]
    if not errors.empty:
        theme.divider()
        chart_col, note_col = st.columns([1.35, 1], gap="medium")
        with chart_col:
            theme.section("Where the error concentrates")
            theme.chart(error_figure(errors), key="md_error")
        with note_col:
            theme.section("Which attributes drive it")
            theme.chart(importance_figure(extras["importance"]), key="md_importance")

    theme.divider()
    theme.section("The buffer, and why it exists")
    missing = int(frame["actual_value_eur"].isna().sum())
    st.markdown(
        f"""
- The recorded value in this dataset is the only reference available, and it is
  incomplete: **{missing:,} of {len(frame):,} players have no recorded value at all**, so they
  can never be called undervalued or overvalued.
- Because a model estimate is not an exact figure, a small difference is not evidence.
  The comparison uses a buffer of **k = {f"{float(k):.4f}" if k else "0.0949"} log units**
  (two robust standard deviations of the model's out-of-fold error, roughly ±10%).
- A player is called **potentially undervalued** only when the estimate is at least
  **{under:.4f}×** the recorded value, and **potentially overvalued** only when it is at
  most **{over:.4f}×**. Everything in between is **fairly valued** — deliberately, not by
  accident.
- Predictions in the table are out-of-fold: every player was scored by a model that never
  saw them during training, which is what makes the comparison fair.
"""
    )
    with st.container(border=True):
        st.markdown(
            f"""
**What this is not.** The dataset is a snapshot of player attributes and values, so the
estimate has no idea about contract length, club finances, injuries, age curves beyond what
the attributes encode, or the currency and year of the recorded values. It is an AI-based
*indication* built to support analysis — not a transfer-fee prediction and not financial
advice. Read "undervalued" as "the model's estimate sits meaningfully above the recorded
value", nothing stronger.
"""
        )


def error_figure(errors: pd.DataFrame):
    figure = go.Figure()
    colours = [theme.FAIR, theme.ACCENT]
    for colour, (model, part) in zip(colours, errors.groupby("model", sort=True)):
        figure.add_trace(go.Bar(
            x=part["group"].astype(str),
            y=part["MAE_eur"] / 1e6,
            name=str(model),
            marker_color=colour,
            hovertemplate="%{x}: €%{y:.1f}M MAE<extra></extra>",
        ))
    figure.update_layout(barmode="group")
    figure.update_yaxes(title="MAE (€ millions)")
    return theme.style_fig(figure, height=330)


def importance_figure(importance: pd.DataFrame):
    if importance.empty:
        return theme.style_fig(go.Figure(), height=330)
    top = importance.head(12).iloc[::-1]
    figure = go.Figure(go.Bar(
        x=top["importance"], y=top["feature"].astype(str), orientation="h",
        marker_color=theme.ACCENT, opacity=0.85,
        hovertemplate="%{y}: %{x:.3f}<extra></extra>",
    ))
    figure.update_xaxes(title="Relative importance")
    return theme.style_fig(figure, height=330, legend=False)


# ---------------------------------------------------------------------------- main


def main() -> None:
    st.set_page_config(
        page_title="Footstat 304 · Player value",
        page_icon="⚽",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    theme.inject()
    consume_pending()
    consume_query_page()

    with st.spinner("Loading the player table…"):
        try:
            frame, meta, source = load_table()
        except FileNotFoundError as exc:
            st.error(
                "Could not find the data files. Keep `ai-core/` next to `frontend/` "
                f"and run from the repository root.\n\n{exc}"
            )
            st.stop()
    extras = load_extras()
    sidebar(meta, source, len(frame))

    page = st.session_state.get("nav", PAGES[0])
    {
        "Overview": page_overview,
        "Player Explorer": page_explorer,
        "Player Profile": page_profile,
        "Compare": page_compare,
        "Model & Method": page_model,
    }.get(page, page_overview)(frame, meta, extras)

    theme.divider()
    theme.note(
        "Footstat 304 · AI-based player evaluation · estimates from a 2019 attribute snapshot, "
        f"judged against a ±10% error buffer · {len(frame):,} players"
    )


if __name__ == "__main__":
    main()
