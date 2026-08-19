"""Plotly figures for the cascade app.

Colours come from the validated data-viz palette.  Two encodings are in play:

* **Categorical** -- species identity within a panel.  Slots are assigned by
  *role in the cascade*, so the two mirrored stages share colours: E and F are
  both the free enzyme, EA and FB both the complex, EAact and FBact both the
  activated complex.  The grid is laid out so the two stages read as the same
  picture twice, and no colour is ever repeated inside one panel.  The set
  actually drawn together validates all-pairs in both modes (worst CVD dE 9.1
  light / 8.4 dark).
* **Sequential** -- A0 magnitude in a sweep.  One hue, light->dark, so a darker
  curve is a higher dose.  Per-curve identity is carried by the legend, the
  hover readout and the table view, not by colour alone: past ~8 curves the
  ramp cannot hold a 0.06 lightness gap between neighbours, so it is read as a
  gradient rather than as individually nameable steps.

Light-mode aqua and yellow sit below 3:1 on the light surface, so the relief
rule applies -- the app always ships the table view alongside these figures.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .simulate import SWEEP_COLUMN, TIME_COLUMN, rate_column

# --- theme tokens ------------------------------------------------------------

THEMES: dict[str, dict[str, str]] = {
    "light": {
        "text_primary": "#0b0b0b",
        "text_secondary": "#52514e",
        "muted": "#898781",
        "grid": "#e1e0d9",
        "axis": "#c3c2b7",
    },
    "dark": {
        "text_primary": "#ffffff",
        "text_secondary": "#c3c2b7",
        "muted": "#898781",
        "grid": "#2c2c2a",
        "axis": "#383835",
    },
}

# Categorical slots, in the palette's fixed order.
_SLOTS: dict[str, dict[str, str]] = {
    "blue": {"light": "#2a78d6", "dark": "#3987e5"},
    "orange": {"light": "#eb6834", "dark": "#d95926"},
    "aqua": {"light": "#1baf7a", "dark": "#199e70"},
    "yellow": {"light": "#eda100", "dark": "#c98500"},
    "magenta": {"light": "#e87ba4", "dark": "#d55181"},
    "violet": {"light": "#4a3aa7", "dark": "#9085e9"},
}

# Species -> slot, by role rather than by order of appearance.
_SPECIES_SLOT: dict[str, str] = {
    "A": "blue",
    "E": "orange",
    "EA": "aqua",
    "EAact": "yellow",
    "B": "magenta",
    "F": "orange",
    "FB": "aqua",
    "FBact": "yellow",
    "C": "violet",
}

# Sequential blue ramp.  Light mode starts at step 250 and dark ends at step
# 600 so the end nearest each surface still clears 2:1.
_RAMP_LIGHT = [
    "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6",
    "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b",
]
_RAMP_DARK = [
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec",
    "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95",
]

class Panel(NamedTuple):
    """One subplot: where it sits, what it is called, what it draws."""

    row: int
    col: int
    title: str
    species: tuple[str, ...]


# Cascade.m:35-38 puts A and E on one pair of axes, but E is ~10^4 while A, EA
# and EAact are ~10^1, so on a linear scale three of the four curves collapse
# onto the baseline.  Two magnitudes belong in two charts, never on two y-axes,
# so rows 1-2 give every panel a single order of magnitude.  The rows are the
# two mirrored stages and the columns line up their counterparts:
# complexes | free enzyme | stage output.
PANELS: tuple[Panel, ...] = (
    Panel(1, 1, "Stage 1 — complexes", ("A", "EA", "EAact")),
    Panel(1, 2, "Stage 1 — free enzyme", ("E",)),
    Panel(1, 3, "Messenger B", ("B",)),
    Panel(2, 1, "Stage 2 — complexes", ("FB", "FBact")),
    Panel(2, 2, "Stage 2 — free enzyme", ("F",)),
    Panel(2, 3, "Output C", ("C",)),
)

# Rates span seven orders of magnitude and do *not* follow the concentration
# groupings -- dA/dt peaks at ~1155 while dEAact/dt peaks at 0.077, though both
# belong to stage 1.  So the rate panels are grouped strictly by magnitude
# band, which needs two rows to keep every panel inside one band.
RATE_PANELS: tuple[Panel, ...] = (
    Panel(3, 1, "Binding burst — d/dt", ("A", "E", "EA")),
    Panel(3, 2, "Output production — d/dt", ("C",)),
    Panel(3, 3, "Stage 2 transfer — d/dt", ("F", "FB", "FBact")),
    Panel(4, 1, "Activation — d/dt", ("EAact",)),
    Panel(4, 2, "Messenger turnover — d/dt", ("B",)),
)

# dA/dt and dE/dt reduce to the same expression for every parameter value, so
# the two curves coincide.  Dashing one keeps the other from hiding it.
RATE_DASHED: frozenset[str] = frozenset({"E"})

GRID_ROWS, GRID_COLS = 4, 3

# Key readouts overlaid across doses when sweeping.
SWEEP_PANELS: tuple[tuple[str, str], ...] = (
    ("Activated EA", "EAact"),
    ("Messenger B", "B"),
    ("Activated FB", "FBact"),
    ("Output C", "C"),
)


def species_color(species: str, theme: str) -> str:
    return _SLOTS[_SPECIES_SLOT[species]][theme]


def ramp_colors(n: int, theme: str) -> list[str]:
    """Sample the sequential ramp at n points, ends inclusive."""
    ramp = _RAMP_LIGHT if theme == "light" else _RAMP_DARK
    if n <= 1:
        return [ramp[-1]]
    idx = np.linspace(0, len(ramp) - 1, n)
    return [ramp[int(round(i))] for i in idx]


def _style(fig: go.Figure, theme: str, height: int, y_type: str | None = None) -> go.Figure:
    tokens = THEMES[theme]
    fig.update_layout(
        height=height,
        margin=dict(l=60, r=24, t=56, b=48),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family='system-ui, -apple-system, "Segoe UI", sans-serif',
            size=13,
            color=tokens["text_secondary"],
        ),
        hovermode="x unified",
        hoverlabel=dict(font_size=12),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.16,
            x=0,
            font=dict(color=tokens["text_secondary"]),
        ),
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor=tokens["grid"],
        gridwidth=1,
        zeroline=False,
        linecolor=tokens["axis"],
        ticks="outside",
        tickcolor=tokens["axis"],
        tickfont=dict(color=tokens["muted"]),
        showspikes=True,
        spikemode="across",
        spikethickness=1,
        spikecolor=tokens["axis"],
        spikedash="dot",
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=tokens["grid"],
        gridwidth=1,
        zeroline=False,
        linecolor=tokens["axis"],
        ticks="outside",
        tickcolor=tokens["axis"],
        tickfont=dict(color=tokens["muted"]),
    )
    if y_type is not None:
        fig.update_yaxes(type=y_type)
    for annotation in fig.layout.annotations:
        annotation.font.color = tokens["text_primary"]
        annotation.font.size = 13
    return fig


def _subplot_titles() -> list[str]:
    """Row-major titles, with a blank for the unused cell in the last row."""
    titles = {(panel.row, panel.col): panel.title for panel in PANELS + RATE_PANELS}
    return [
        titles.get((row, col), "")
        for row in range(1, GRID_ROWS + 1)
        for col in range(1, GRID_COLS + 1)
    ]


def timecourse_grid(
    frame,
    rate_frame=None,
    theme: str = "light",
    y_type: str = "linear",
    conc_unit: str = "pmol/L",
    time_unit: str = "s",
) -> go.Figure:
    """Every species by magnitude band, and -- when rates are supplied -- their
    rates of change on the two rows beneath, sharing the same time axis."""
    tokens = THEMES[theme]
    panels = PANELS + (RATE_PANELS if rate_frame is not None else ())
    rows = GRID_ROWS if rate_frame is not None else 2

    fig = make_subplots(
        rows=rows,
        cols=GRID_COLS,
        subplot_titles=_subplot_titles()[: rows * GRID_COLS],
        horizontal_spacing=0.08,
        vertical_spacing=0.09 if rate_frame is not None else 0.17,
    )

    legended: set[str] = set()
    for panel in panels:
        is_rate = panel in RATE_PANELS
        source = rate_frame if is_rate else frame
        if source is None or not len(source):
            continue

        for position, species in enumerate(panel.species):
            column = rate_column(species) if is_rate else species
            label = f"d{species}/dt" if is_rate else species
            color = species_color(species, theme)

            # One legend entry per species, taken the first time it appears in
            # a panel that draws more than one curve; a lone curve is named by
            # its panel title instead.
            show_legend = len(panel.species) > 1 and species not in legended
            if show_legend:
                legended.add(species)

            fig.add_trace(
                go.Scatter(
                    x=source[TIME_COLUMN],
                    y=source[column],
                    name=species,
                    legendgroup=species,
                    mode="lines",
                    line=dict(
                        color=color,
                        width=2,
                        dash="dash" if is_rate and species in RATE_DASHED else "solid",
                    ),
                    hovertemplate=(
                        f"{label} %{{y:.4g}} {conc_unit}"
                        + (f"/{time_unit}" if is_rate else "")
                        + "<extra></extra>"
                    ),
                    showlegend=show_legend,
                ),
                row=panel.row,
                col=panel.col,
            )

            if len(panel.species) > 1:
                # A direct label at the line end, so identity never rests on
                # colour alone.  Anchors alternate to keep close curves legible.
                fig.add_annotation(
                    x=float(source[TIME_COLUMN].iloc[-1]),
                    y=float(source[column].iloc[-1]),
                    text=label,
                    showarrow=False,
                    xanchor="right",
                    yanchor="bottom" if position % 2 == 0 else "top",
                    yshift=4 if position % 2 == 0 else -4,
                    font=dict(color=tokens["text_secondary"], size=11),
                    row=panel.row,
                    col=panel.col,
                )

    # The x title goes on the lowest panel of each column, since the last row
    # is short one cell.
    for col in range(1, GRID_COLS + 1):
        lowest = max(panel.row for panel in panels if panel.col == col)
        fig.update_xaxes(title_text=f"Time ({time_unit})", row=lowest, col=col)

    fig.update_yaxes(title_text=f"Concentration ({conc_unit})", row=1, col=1)
    fig.update_yaxes(title_text=f"Concentration ({conc_unit})", row=2, col=1)
    # Only the concentration rows follow the linear/log choice: rates are
    # signed -- dA/dt, dE/dt and dF/dt are negative throughout -- and a log
    # axis would silently drop them.
    fig.update_yaxes(type=y_type, row=1)
    fig.update_yaxes(type=y_type, row=2)
    if rate_frame is not None:
        fig.update_yaxes(title_text=f"Rate ({conc_unit}/{time_unit})", row=3, col=1)
        fig.update_yaxes(title_text=f"Rate ({conc_unit}/{time_unit})", row=4, col=1)
        fig.update_yaxes(type="linear", row=3)
        fig.update_yaxes(type="linear", row=4)

    return _style(fig, theme, height=1180 if rate_frame is not None else 660)


def sweep_grid(
    frame,
    theme: str = "light",
    y_type: str = "linear",
    conc_unit: str = "pmol/L",
    time_unit: str = "s",
) -> go.Figure:
    """Key readouts across every swept A0, coloured light->dark by dose."""
    doses = sorted(frame[SWEEP_COLUMN].unique())
    colors = ramp_colors(len(doses), theme)

    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=[title for title, _ in SWEEP_PANELS],
        horizontal_spacing=0.1,
        vertical_spacing=0.16,
    )

    for index, (_, species) in enumerate(SWEEP_PANELS):
        row, col = divmod(index, 2)
        for dose, color in zip(doses, colors):
            subset = frame[frame[SWEEP_COLUMN] == dose]
            label = f"A0 = {dose:g}"
            fig.add_trace(
                go.Scatter(
                    x=subset[TIME_COLUMN],
                    y=subset[species],
                    name=label,
                    legendgroup=label,
                    mode="lines",
                    line=dict(color=color, width=2),
                    hovertemplate=(
                        f"{label} — {species} %{{y:.4g}} {conc_unit}<extra></extra>"
                    ),
                    showlegend=index == 0,
                ),
                row=row + 1,
                col=col + 1,
            )

    fig.update_xaxes(title_text=f"Time ({time_unit})", row=2)
    fig.update_yaxes(title_text=f"Concentration ({conc_unit})", col=1)
    return _style(fig, theme, height=620, y_type=y_type)


def dose_response(
    frame,
    t_end: float,
    theme: str = "light",
    conc_unit: str = "pmol/L",
    time_unit: str = "s",
) -> go.Figure:
    """C at the final time against A0 -- the closing plot of Cascade.m."""
    tokens = THEMES[theme]
    color = species_color("C", theme)

    fig = go.Figure(
        go.Scatter(
            x=frame["A0"],
            y=frame["C_final"],
            mode="lines+markers",
            line=dict(color=color, width=2),
            marker=dict(size=8, color=color, line=dict(width=2, color="rgba(0,0,0,0)")),
            hovertemplate=(
                f"A0 %{{x:g}} {conc_unit}<br>C %{{y:.4g}} {conc_unit}<extra></extra>"
            ),
            showlegend=False,
        )
    )
    # One direct label at the top dose, rather than a number on every point.
    if len(frame):
        last = frame.iloc[-1]
        fig.add_annotation(
            x=float(last["A0"]),
            y=float(last["C_final"]),
            text=f"{last['C_final']:,.0f}",
            showarrow=False,
            xanchor="right",
            yanchor="bottom",
            font=dict(color=tokens["text_primary"], size=12),
        )

    fig.update_layout(
        title=dict(
            text=f"Output C at t = {t_end:g} {time_unit}",
            font=dict(color=tokens["text_primary"], size=15),
        )
    )
    fig.update_xaxes(title_text=f"Initial analyte A0 ({conc_unit})")
    fig.update_yaxes(title_text=f"C ({conc_unit})")
    return _style(fig, theme, height=380, y_type="linear")
