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
GRID = "rgba(255,255,255,0.055)"
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
  --surface: #0F1728;
  --line: #1F2C45;
  --text: #E9EEF8;
  --muted: #8FA0BA;
  --accent: #5EEAD4;
}
.block-container { padding-top: 2.6rem; padding-bottom: 3.2rem; max-width: 1340px; }
header[data-testid="stHeader"] { background: transparent; }
section[data-testid="stSidebar"] { background: #0A101C; border-right: 1px solid var(--line); }
section[data-testid="stSidebar"] .block-container { padding-top: 1.8rem; }

.fs-eyebrow {
  font-size: 10.5px; letter-spacing: .2em; text-transform: uppercase;
  color: var(--accent); font-weight: 650; margin-bottom: .4rem;
}
.fs-h1 { font-size: 29px; font-weight: 680; letter-spacing: -.025em; color: var(--text); line-height: 1.15; }
.fs-hero {
  background: linear-gradient(135deg, #121D31 0%, #0B1320 65%);
  border: 1px solid var(--line); border-radius: 18px;
  padding: 20px 22px 18px 22px; margin: .2rem 0 1rem 0;
}
.fs-hero .fs-h1 { font-size: 26px; margin-bottom: .2rem; }
.fs-hero-meta { color: var(--muted); font-size: 13px; margin-top: .35rem; }
.fs-hero-row { display: flex; gap: 18px; align-items: center; }
.fs-hero-body { min-width: 0; }
.fs-hero-art {
  width: 104px; height: 128px; flex: 0 0 auto; border-radius: 13px;
  object-fit: cover; object-position: top center;
  background: #16233A; border: 1px solid var(--line);
}
.fs-hero-plate {
  display: flex; align-items: center; justify-content: center;
  font-size: 32px; font-weight: 650; color: var(--muted); letter-spacing: .02em;
}
.fs-face {
  display: flex; align-items: center; justify-content: center; border-radius: 13px;
  background: linear-gradient(160deg, #18253C 0%, #101A2B 100%);
  border: 1px solid var(--line); color: var(--muted);
  font-size: 20px; font-weight: 650; letter-spacing: .04em;
}
.fs-mini {
  font-size: 12.5px; font-weight: 650; color: var(--text); margin-top: 7px;
  line-height: 1.25; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.fs-mini-sub { font-size: 11px; color: var(--muted); margin-top: 2px; line-height: 1.35; }
.fs-card {
  background: var(--surface); border: 1px solid var(--line); border-radius: 14px;
  padding: 14px 16px; height: 100%;
}
.fs-label {
  font-size: 10.5px; text-transform: uppercase; letter-spacing: .11em;
  color: var(--muted); font-weight: 650;
}
.fs-value {
  font-size: 25px; font-weight: 650; color: var(--text);
  font-variant-numeric: tabular-nums; line-height: 1.25; margin-top: 5px;
}
.fs-sub { font-size: 12px; color: var(--muted); margin-top: 4px; line-height: 1.4; }
.fs-pill {
  display: inline-block; font-size: 10.5px; letter-spacing: .09em; text-transform: uppercase;
  font-weight: 650; padding: 3px 10px; border-radius: 999px; border: 1px solid;
}
.fs-section {
  font-size: 12px; text-transform: uppercase; letter-spacing: .13em;
  color: var(--muted); font-weight: 650; margin: .6rem 0 .1rem 0;
}
.fs-note { font-size: 12px; color: var(--muted); line-height: 1.5; }
.fs-divider { height: 1px; background: var(--line); margin: 20px 0; border: 0; }
[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 12px; }
.stButton button { border-radius: 9px; font-size: 13px; }
.stDownloadButton button { border-radius: 9px; }
div[data-testid="stMetricValue"] { font-size: 23px; font-variant-numeric: tabular-nums; }
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
    sub_html = f'<div class="fs-sub" style="font-size:13px;max-width:78ch">{esc(sub)}</div>' if sub else ""
    st.markdown(
        f'<div class="fs-eyebrow">{esc(eyebrow)}</div>'
        f'<div class="fs-h1">{esc(title)}</div>{sub_html}',
        unsafe_allow_html=True,
    )


def stat(label: str, value: str, sub: str = "", color: str = TEXT) -> None:
    sub_html = f'<div class="fs-sub">{esc(sub)}</div>' if sub else ""
    st.markdown(
        f'<div class="fs-card"><div class="fs-label">{esc(label)}</div>'
        f'<div class="fs-value" style="color:{color}">{esc(value)}</div>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def section(title: str, sub: str = "") -> None:
    extra = f'<span style="text-transform:none;letter-spacing:0"> · {esc(sub)}</span>' if sub else ""
    st.markdown(f'<div class="fs-section">{esc(title)}{extra}</div>', unsafe_allow_html=True)


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
        margin=dict(l=12, r=12, t=34 if legend else 12, b=12),
        height=height,
        hoverlabel=dict(bgcolor=SURFACE_2, bordercolor=LINE, font=dict(color=TEXT, size=12, family=FONT)),
        showlegend=legend,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, x=0,
            font=dict(size=11, color=MUTED), bgcolor="rgba(0,0,0,0)",
        ),
        bargap=0.3,
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(range=[0, 100], gridcolor=GRID, linecolor=LINE,
                            tickfont=dict(size=9, color=MUTED), angle=90),
            angularaxis=dict(gridcolor=GRID, linecolor=LINE, tickfont=dict(size=11, color=TEXT)),
        ),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=LINE,
                     tickfont=dict(color=MUTED, size=11), title_font=dict(color=MUTED, size=11))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=LINE,
                     tickfont=dict(color=MUTED, size=11), title_font=dict(color=MUTED, size=11))
    return fig


def chart(fig, key: str | None = None) -> None:
    """Render a Plotly figure at full width, across Streamlit versions."""
    kwargs = dict(theme=None, config={"displayModeBar": False, "responsive": True})
    try:
        st.plotly_chart(fig, width="stretch", key=key, **kwargs)
    except TypeError:  # Streamlit before the width= API
        st.plotly_chart(fig, use_container_width=True, key=key, **kwargs)
