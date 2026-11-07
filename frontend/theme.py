"""Visual language for the Footstat dashboard: tokens, stylesheet, chart defaults.

Kept separate from ``app.py`` so colours, spacing and card markup live in one
place. Every value here mirrors the CSS custom properties at the top of ``CSS``.
"""

from __future__ import annotations

import html

import streamlit as st

INK = "#080D17"
SURFACE = "#0F1728"
SURFACE_2 = "#141E31"
LINE = "#1F2C45"
GRID = "rgba(148,163,184,0.09)"
TEXT = "#E9EEF8"
MUTED = "#8FA0BA"
ACCENT = "#5EEAD4"
UNDER = "#34D399"
OVER = "#FBBF24"
FAIR = "#94A3B8"
NEUTRAL = "#64748B"
FONT = "Inter, 'Segoe UI', system-ui, -apple-system, sans-serif"

EVAL_COLOR = {
    "Potentially Undervalued": UNDER,
    "Fairly Valued": FAIR,
    "Potentially Overvalued": OVER,
    "No recorded value": NEUTRAL,
}
EVAL_SHORT = {
    "Potentially Undervalued": "Undervalued",
    "Fairly Valued": "Fairly valued",
    "Potentially Overvalued": "Overvalued",
    "No recorded value": "No recorded value",
}

CSS = """
<style>
:root {
  --ink: #080D17;
  --surface: #0E1626;
  --line: rgba(148, 163, 184, 0.14);
  --line-strong: rgba(148, 163, 184, 0.24);
  --text: #E9EEF8;
  --muted: #8FA0BA;
  --faint: #64748B;
  --accent: #5EEAD4;
  --violet: #A78BFA;
}

/* ---------- canvas ---------- */
.stApp {
  background:
    radial-gradient(1100px 520px at 85% -12%, rgba(94, 234, 212, 0.07), transparent 62%),
    radial-gradient(900px 480px at -8% -6%, rgba(167, 139, 250, 0.06), transparent 60%),
    var(--ink);
}
.stApp, .stApp p, .stApp li { font-feature-settings: "cv11", "ss01", "tnum"; }
.block-container { padding-top: 2.4rem; padding-bottom: 2.6rem; max-width: 1320px; }
header[data-testid="stHeader"] { background: transparent; }
[data-testid="stAppDeployButton"], [data-testid="stToolbarActions"] { display: none !important; }
[data-testid="stElementToolbar"] { display: none; }

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"] {
  width: 252px !important; min-width: 252px !important;
  background: linear-gradient(180deg, #0B1220 0%, #080D17 100%);
  border-right: 1px solid var(--line);
}
section[data-testid="stSidebar"] .block-container,
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding-top: 1.4rem; }
.fs-brand { display: flex; align-items: center; gap: 11px; margin: 0 0 1.4rem 2px; }
.fs-logo {
  width: 36px; height: 36px; border-radius: 10px; flex: 0 0 auto;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 800; letter-spacing: -.02em; color: #06201C;
  background: linear-gradient(140deg, #7FF5E1 0%, #5EEAD4 45%, #38BDF8 100%);
  box-shadow: 0 6px 18px -6px rgba(94, 234, 212, .55);
}
.fs-brand-name { font-size: 15px; font-weight: 700; color: var(--text); letter-spacing: -.01em; line-height: 1.2; }
.fs-brand-sub { font-size: 11.5px; color: var(--muted); margin-top: 1px; }
.fs-nav-label {
  font-size: 10.5px; letter-spacing: .14em; text-transform: uppercase; color: var(--faint);
  font-weight: 650; margin: 0 0 .35rem 4px;
}
section[data-testid="stSidebar"] [data-testid="stElementContainer"]:has([data-testid="stRadio"]),
section[data-testid="stSidebar"] [data-testid="stRadio"],
section[data-testid="stSidebar"] [data-testid="stRadio"] > div,
section[data-testid="stSidebar"] [role="radiogroup"] { gap: 3px; width: 100% !important; }
section[data-testid="stSidebar"] [role="radiogroup"] > div { width: 100%; display: block; }
section[data-testid="stSidebar"] [data-testid="stRadioOption"] {
  display: flex; width: 100%; margin: 0; padding: 8px 12px; border-radius: 9px; box-sizing: border-box;
  border: 1px solid transparent; transition: background .15s, border-color .15s; cursor: pointer;
}
section[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div:first-child { display: none; }
section[data-testid="stSidebar"] [data-testid="stRadioOption"] p { font-size: 14px; color: var(--muted); font-weight: 500; }
section[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover { background: rgba(148, 163, 184, .07); }
section[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] {
  background: rgba(94, 234, 212, .09); border-color: rgba(94, 234, 212, .22);
  box-shadow: inset 3px 0 0 var(--accent);
}
section[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] p { color: var(--text); font-weight: 600; }
.fs-status {
  border: 1px solid var(--line); border-radius: 12px; padding: 12px 13px;
  background: rgba(255, 255, 255, .02);
}
.fs-status-row { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; color: var(--text); }
.fs-dot { width: 8px; height: 8px; border-radius: 50%; flex: 0 0 auto; }
.fs-status .fs-note { margin-top: 6px; word-break: break-word; }

/* ---------- page header ---------- */
.fs-eyebrow {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 11px; letter-spacing: .16em; text-transform: uppercase;
  color: var(--accent); font-weight: 650; margin-bottom: .55rem;
}
.fs-eyebrow::before { content: ""; width: 18px; height: 2px; border-radius: 2px; background: var(--accent); }
.fs-h1 {
  font-size: 34px; font-weight: 750; letter-spacing: -.032em; line-height: 1.12;
  background: linear-gradient(180deg, #FFFFFF 0%, #C9D4E6 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.fs-lede { font-size: 14.5px; color: var(--muted); line-height: 1.6; max-width: 78ch; margin-top: .55rem; }
.fs-head { margin-bottom: 1.5rem; }

/* ---------- cards ---------- */
.fs-card {
  position: relative; overflow: hidden; box-sizing: border-box;
  background: linear-gradient(180deg, rgba(255, 255, 255, .035) 0%, rgba(255, 255, 255, .012) 100%), var(--surface);
  border: 1px solid var(--line); border-radius: 16px;
  padding: 17px 19px 16px 19px; min-height: 138px;
  display: flex; flex-direction: column;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .04), 0 12px 32px -22px rgba(0, 0, 0, .8);
  transition: border-color .2s, transform .2s;
}
.fs-card::before {
  content: ""; position: absolute; left: 0; right: 0; top: 0; height: 2px;
  background: linear-gradient(90deg, var(--c, var(--accent)) 0%, transparent 85%); opacity: .75;
}
.fs-card:hover { border-color: var(--line-strong); transform: translateY(-1px); }
.fs-label {
  display: flex; align-items: center; gap: 7px;
  font-size: 11px; text-transform: uppercase; letter-spacing: .1em;
  color: var(--muted); font-weight: 650; line-height: 1.3;
}
.fs-label::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--c, var(--accent)); flex: 0 0 auto; }
.fs-value {
  font-size: clamp(21px, 1.9vw, 30px); font-weight: 700; color: var(--text);
  letter-spacing: -.025em; line-height: 1.15; margin-top: 10px;
  font-variant-numeric: tabular-nums; overflow-wrap: anywhere;
}
.fs-value.fs-text { font-size: clamp(18px, 1.5vw, 24px); letter-spacing: -.015em; margin-top: 12px; }
.fs-sub {
  font-size: 12.5px; color: var(--muted); margin-top: 6px; line-height: 1.45;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.fs-card .fs-pill { margin-top: 12px; align-self: flex-start; }
.fs-pill {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 11px; letter-spacing: .06em; text-transform: uppercase;
  font-weight: 650; padding: 4px 11px; border-radius: 999px; border: 1px solid;
}
.fs-pill::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }

/* ---------- sections ---------- */
.fs-section { margin: .9rem 0 .55rem 0; }
.fs-section-title { font-size: 15.5px; font-weight: 650; color: var(--text); letter-spacing: -.01em; }
.fs-section-sub { font-size: 12.5px; color: var(--muted); margin-top: 2px; }
.fs-note { font-size: 12.5px; color: var(--muted); line-height: 1.55; }
.fs-note b { color: var(--text); font-weight: 600; }
.fs-divider { height: 1px; border: 0; margin: 28px 0 18px 0;
  background: linear-gradient(90deg, transparent, var(--line-strong) 15%, var(--line-strong) 85%, transparent); }
.fs-footer { display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap;
  font-size: 12px; color: var(--faint); }

/* ---------- player tiles ---------- */
.fs-tile-name {
  font-size: 13.5px; font-weight: 650; color: var(--text); margin-top: 10px;
  line-height: 1.25; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.fs-tile-sub { font-size: 12px; color: var(--muted); margin-top: 3px; line-height: 1.4; }
.fs-tile-sub b { color: var(--text); font-weight: 600; }
.fs-photo {
  width: 100%; aspect-ratio: 4 / 5; object-fit: cover; object-position: center top;
  border-radius: 14px; border: 1px solid var(--line); display: block;
  background: radial-gradient(120% 80% at 50% 0%, #1B2A44 0%, #0E1626 70%);
  box-shadow: 0 14px 30px -20px rgba(0, 0, 0, .9);
  transition: transform .2s, border-color .2s;
}
.fs-photo:hover { transform: translateY(-2px); border-color: rgba(94, 234, 212, .35); }
.fs-face {
  display: flex; align-items: center; justify-content: center; border-radius: 14px;
  aspect-ratio: 4 / 5; width: 100%;
  background: radial-gradient(120% 80% at 50% 0%, #1B2A44 0%, #0E1626 70%);
  border: 1px solid var(--line); color: var(--muted);
  font-size: 22px; font-weight: 700; letter-spacing: .04em;
}

/* ---------- profile hero ---------- */
.fs-hero {
  position: relative; overflow: hidden;
  background:
    radial-gradient(600px 220px at 100% 0%, rgba(94, 234, 212, .10), transparent 70%),
    linear-gradient(135deg, #111C30 0%, #0B1322 70%);
  border: 1px solid var(--line); border-radius: 20px;
  padding: 22px 24px; margin: .4rem 0 1.1rem 0;
}
.fs-hero .fs-h1 { font-size: 30px; }
.fs-hero-meta { color: var(--muted); font-size: 13.5px; margin-top: .45rem; line-height: 1.5; }
.fs-hero-row { display: flex; gap: 22px; align-items: center; }
.fs-hero-body { min-width: 0; }
.fs-hero-art {
  width: 112px; height: 140px; flex: 0 0 auto; border-radius: 14px;
  object-fit: cover; object-position: top center;
  background: #16233A; border: 1px solid var(--line-strong);
  box-shadow: 0 16px 34px -20px rgba(0, 0, 0, .95);
}
.fs-hero-plate {
  display: flex; align-items: center; justify-content: center;
  font-size: 32px; font-weight: 700; color: var(--muted); letter-spacing: .02em;
}

/* ---------- streamlit widgets ---------- */
[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 16px; }
.stButton button, .stDownloadButton button {
  border-radius: 9px; font-size: 13px; font-weight: 550;
  border: 1px solid var(--line-strong); background: rgba(255, 255, 255, .025);
  transition: border-color .15s, background .15s, color .15s;
}
.stButton button:hover:not(:disabled) {
  border-color: rgba(94, 234, 212, .55); color: var(--accent); background: rgba(94, 234, 212, .06);
}
.stMarkdown ul li { margin-bottom: .35rem; color: #CBD5E4; }
.stMarkdown strong { color: var(--text); }
div[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
</style>
"""


def inject() -> None:
    """Apply the stylesheet once per run."""
    st.markdown(CSS, unsafe_allow_html=True)


def esc(value) -> str:
    return html.escape(str(value))


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"


def pill(text: str, color: str = ACCENT) -> str:
    return (
        f'<span class="fs-pill" style="color:{color};border-color:{rgba(color, 0.45)};'
        f'background:{rgba(color, 0.12)}">{esc(text)}</span>'
    )


def header(eyebrow: str, title: str, sub: str = "") -> None:
    sub_html = f'<div class="fs-lede">{esc(sub)}</div>' if sub else ""
    st.markdown(
        f'<div class="fs-head"><div class="fs-eyebrow">{esc(eyebrow)}</div>'
        f'<div class="fs-h1">{esc(title)}</div>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def stat(label: str, value: str, sub: str = "", color: str = TEXT, badge: str = "",
         accent: str | None = None) -> None:
    """A card with a label, a big value, a sub-line and an optional badge (trusted HTML).

    Nothing is cut off: the value scales with the window and wraps if it must,
    and the sub-line wraps onto a second line.
    """
    dot = accent or (color if color != TEXT else ACCENT)
    sub_html = f'<div class="fs-sub" title="{esc(sub)}">{esc(sub)}</div>' if sub else ""
    # Words (e.g. "Random forest") get a calmer size than figures, so they stay on one line.
    kind = "fs-value" if any(ch.isdigit() for ch in str(value)) or len(str(value)) < 3 else "fs-value fs-text"
    st.markdown(
        f'<div class="fs-card" style="--c:{dot}"><div class="fs-label">{esc(label)}</div>'
        f'<div class="{kind}" style="color:{color}">{esc(value)}</div>{sub_html}{badge}</div>',
        unsafe_allow_html=True,
    )


def section(title: str, sub: str = "") -> None:
    sub_html = f'<div class="fs-section-sub">{esc(sub)}</div>' if sub else ""
    st.markdown(
        f'<div class="fs-section"><div class="fs-section-title">{esc(title)}</div>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def note(html_text: str) -> None:
    """Render a small muted paragraph. ``html_text`` must be trusted markup."""
    st.markdown(f'<div class="fs-note">{html_text}</div>', unsafe_allow_html=True)


def divider() -> None:
    st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)


def style_fig(fig, height: int = 320, legend: bool = True):
    """Apply the dashboard's chart defaults to a Plotly figure."""
    fig.update_layout(
        template=None,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=12, color=MUTED),
        title_font=dict(family=FONT, color=TEXT),
        margin=dict(l=8, r=16, t=40 if legend else 12, b=8),
        height=height,
        hoverlabel=dict(bgcolor=SURFACE_2, bordercolor=LINE, font=dict(color=TEXT, size=12, family=FONT)),
        showlegend=legend,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, x=0,
            font=dict(size=11, color=MUTED), bgcolor="rgba(0,0,0,0)",
        ),
        bargap=0.3,
        barcornerradius=4,
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(range=[0, 100], gridcolor=GRID, linecolor="rgba(0,0,0,0)",
                            showticklabels=False, ticks="", angle=90),
            angularaxis=dict(gridcolor=GRID, linecolor="rgba(148,163,184,0.18)", tickfont=dict(size=12, color=TEXT)),
        ),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor="rgba(148,163,184,0.18)", automargin=True, title_standoff=12,
                     tickfont=dict(color=MUTED, size=11), title_font=dict(color=MUTED, size=12))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor="rgba(148,163,184,0.18)", automargin=True, title_standoff=12,
                     tickfont=dict(color=MUTED, size=11), title_font=dict(color=MUTED, size=12))
    return fig


def chart(fig, key: str | None = None) -> None:
    """Render a Plotly figure at full width, across Streamlit versions."""
    kwargs = dict(theme=None, config={"displayModeBar": False, "responsive": True})
    try:
        st.plotly_chart(fig, width="stretch", key=key, **kwargs)
    except TypeError:  # Streamlit before the width= API
        st.plotly_chart(fig, use_container_width=True, key=key, **kwargs)
