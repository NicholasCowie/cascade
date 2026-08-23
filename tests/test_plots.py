"""Design invariants for the figures.

These encode the rules the charts were built to: one magnitude band per panel,
no repeated colour inside a panel, identity never carried by colour alone, and
units on the axes.
"""

from __future__ import annotations

import pytest

from cascade.model import SPECIES
from cascade.params import load_defaults
from cascade.plots import (
    GRID_COLS,
    GRID_ROWS,
    PANELS,
    RATE_DASHED,
    RATE_PANELS,
    SWEEP_PANELS,
    dose_response,
    ramp_colors,
    species_color,
    sweep_grid,
    timecourse_grid,
)
from cascade.simulate import rate_column, rates, run_single, run_sweep


@pytest.fixture(scope="module")
def params():
    return load_defaults()[0]


@pytest.fixture(scope="module")
def single(params):
    return run_single(params)


@pytest.fixture(scope="module")
def rate_frame(params, single):
    return rates(single, params)


@pytest.fixture(scope="module")
def swept(params):
    return run_sweep(params)


def test_every_species_appears_exactly_once(single):
    plotted = [name for panel in PANELS for name in panel.species]
    assert sorted(plotted) == sorted(SPECIES)


def test_every_species_has_its_rate_plotted_exactly_once():
    plotted = [name for panel in RATE_PANELS for name in panel.species]
    assert sorted(plotted) == sorted(SPECIES)


def test_panels_fit_the_grid_without_overlapping():
    cells = [(panel.row, panel.col) for panel in PANELS + RATE_PANELS]
    assert len(cells) == len(set(cells)), "two panels share a cell"
    assert all(1 <= row <= GRID_ROWS and 1 <= col <= GRID_COLS for row, col in cells)
    # Rows 1-2 are concentrations, rows 3-4 rates; one cell is left empty.
    assert {panel.row for panel in PANELS} == {1, 2}
    assert {panel.row for panel in RATE_PANELS} == {3, 4}
    assert len(cells) == GRID_ROWS * GRID_COLS - 1


@pytest.mark.parametrize("panel", PANELS + RATE_PANELS, ids=lambda p: p.title)
def test_no_colour_is_repeated_inside_a_panel(panel):
    for theme in ("light", "dark"):
        colors = [species_color(name, theme) for name in panel.species]
        assert len(colors) == len(set(colors)), f"{panel.title} repeats a colour"


@pytest.mark.parametrize("panel", PANELS, ids=lambda p: p.title)
def test_each_species_panel_spans_one_order_of_magnitude(panel, single):
    """The reason for splitting E and F out of the MATLAB panels: a series
    500x smaller than its neighbour is invisible on a shared linear axis."""
    peaks = [single[name].max() for name in panel.species]
    assert max(peaks) / min(peaks) < 10, f"{panel.title} mixes magnitudes"


@pytest.mark.parametrize("panel", RATE_PANELS, ids=lambda p: p.title)
def test_each_rate_panel_spans_one_magnitude_band(panel, rate_frame):
    """Rates span seven orders overall, which is why they are grouped by
    magnitude rather than by stage; each panel must still hold one band."""
    peaks = [rate_frame[rate_column(name)].abs().max() for name in panel.species]
    assert max(peaks) / min(peaks) < 10, f"{panel.title} mixes magnitudes"


def test_mirrored_stages_share_role_colours():
    for stage_one, stage_two in (("EA", "FB"), ("EAact", "FBact"), ("E", "F")):
        for theme in ("light", "dark"):
            assert species_color(stage_one, theme) == species_color(stage_two, theme)


def test_each_species_is_legended_at_most_once(single, rate_frame):
    fig = timecourse_grid(single, rate_frame)
    legended = [trace.name for trace in fig.data if trace.showlegend]
    assert len(legended) == len(set(legended)), "duplicate legend entries"

    multi = {
        name
        for panel in PANELS + RATE_PANELS
        if len(panel.species) > 1
        for name in panel.species
    }
    assert set(legended) == multi, "legend covers exactly the multi-series curves"


def test_multi_series_curves_are_directly_labelled(single, rate_frame):
    fig = timecourse_grid(single, rate_frame)
    labels = {a.text for a in fig.layout.annotations}
    for panel in PANELS + RATE_PANELS:
        if len(panel.species) > 1:
            for name in panel.species:
                expected = f"d{name}/dt" if panel in RATE_PANELS else name
                assert expected in labels, f"{expected} has no direct label"


def _panel_axis(panel) -> str:
    """The yref make_subplots gives a panel, row-major from the top left."""
    index = (panel.row - 1) * GRID_COLS + panel.col
    return "y" if index == 1 else f"y{index}"


@pytest.mark.parametrize("y_type", ["linear", "log"])
def test_direct_labels_read_in_the_same_order_as_their_curves(
    single, rate_frame, y_type
):
    """A label at a line end has to read as belonging to that line.

    A ends at 0 with EA barely above it, so a label hung below EA lands beside
    A and the two read as swapped.  Offsetting each label by a tenth of its
    panel -- about what 11px of text takes up in a 200px panel -- and sorting
    by where it actually lands catches that: the labels have to come out in
    the same order as the curves they name.  Their coordinates are checked in
    the space the axis draws, since a log axis positions them in decades.
    """
    from math import log10

    fig = timecourse_grid(single, rate_frame, y_type=y_type)
    annotations = {a.text: a for a in fig.layout.annotations if a.yref != "paper"}

    for panel in PANELS + RATE_PANELS:
        if len(panel.species) < 2:
            continue
        is_rate = panel in RATE_PANELS
        log_axis = y_type == "log" and not is_rate
        frame = rate_frame if is_rate else single

        ends = {}
        for name in panel.species:
            end = float(frame[rate_column(name) if is_rate else name].iloc[-1])
            if log_axis and end <= 0:
                continue  # a log axis cannot show it, so it goes unlabelled
            ends[f"d{name}/dt" if is_rate else name] = log10(end) if log_axis else end

        for label, position in ends.items():
            drawn = annotations[label]
            assert drawn.yref == _panel_axis(panel), f"{label} is on the wrong panel"
            assert drawn.y == pytest.approx(position), f"{label} sits off its line"

        margin = 0.1 * (max(ends.values()) - min(ends.values()))
        placed = {
            label: position + (margin if annotations[label].yanchor == "bottom" else -margin)
            for label, position in ends.items()
        }
        assert sorted(ends, key=ends.get) == sorted(placed, key=placed.get), (
            f"{panel.title}: the labels do not read in the order of their curves"
        )


def test_coincident_rate_curves_are_distinguished(single, rate_frame):
    """dA/dt and dE/dt lie exactly on top of each other, so one is dashed."""
    fig = timecourse_grid(single, rate_frame)
    dashed = {t.name for t in fig.data if t.line.dash == "dash"}
    assert dashed == RATE_DASHED

    import numpy as np

    assert np.allclose(rate_frame["dA_dt"], rate_frame["dE_dt"], atol=1e-15)


def test_rate_axes_stay_linear_under_the_log_toggle(single, rate_frame):
    """Several rates are non-positive throughout, so a log axis would drop
    them entirely.

    They wander a little above zero once the species they consume is exhausted
    and its value hovers on solver noise -- dF/dt is -k4f*B*F, so with F spent
    and B large that noise gets amplified.  Bound it relative to the peak
    rather than absolutely: the excursions stay orders of magnitude below the
    real signal, which is what makes them noise and not a sign change."""
    negative = rate_frame[["dA_dt", "dE_dt", "dF_dt"]]
    peak = negative.min().abs()
    assert (negative.max() <= 1e-5 * peak).all(), "these rates never turn positive"
    assert (peak > 1e-3).all(), "and they are substantially negative"

    fig = timecourse_grid(single, rate_frame, y_type="log")
    layout = fig.layout.to_plotly_json()
    types = {}
    for key in layout:
        if key.startswith("yaxis"):
            index = int(key[5:] or 1)
            types[index] = fig.layout[key].type
    # Axes 1-6 are the concentration panels, 7-11 the rate panels.
    assert all(types[i] == "log" for i in range(1, 7))
    assert all(types[i] == "linear" for i in range(7, 12))


def test_grid_without_rates_keeps_only_the_species_rows(single):
    fig = timecourse_grid(single)
    assert len(fig.data) == sum(len(panel.species) for panel in PANELS)
    assert all(t.line.dash == "solid" for t in fig.data)


def test_axes_carry_units(single, rate_frame):
    fig = timecourse_grid(single, rate_frame, conc_unit="pmol/L", time_unit="s")
    titles = [
        fig.layout[key].title.text
        for key in fig.layout.to_plotly_json()
        if key.startswith(("xaxis", "yaxis")) and fig.layout[key].title.text
    ]
    assert any("Time (s)" == text for text in titles)
    assert any("Concentration (pmol/L)" == text for text in titles)
    assert any("Rate (pmol/L/s)" == text for text in titles)


def test_every_column_gets_a_time_axis_label(single, rate_frame):
    """The last row is short one cell, so the label cannot simply go on row 4."""
    fig = timecourse_grid(single, rate_frame)
    labelled = [
        fig.layout[key].title.text
        for key in fig.layout.to_plotly_json()
        if key.startswith("xaxis") and fig.layout[key].title.text
    ]
    assert len(labelled) == GRID_COLS


def test_log_scale_is_available(single):
    fig = timecourse_grid(single, y_type="log")
    assert fig.layout.yaxis.type == "log"


def test_themes_produce_different_ink_and_series_colours(single):
    light = timecourse_grid(single, theme="light")
    dark = timecourse_grid(single, theme="dark")
    assert light.data[0].line.color != dark.data[0].line.color
    assert light.layout.xaxis.gridcolor != dark.layout.xaxis.gridcolor
    # Transparent backgrounds let the page surface show through in both themes.
    assert light.layout.paper_bgcolor == "rgba(0,0,0,0)"


def _luma(hex_color: str) -> float:
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def test_sweep_ramp_darkens_monotonically_and_never_cycles():
    """Colour encodes dose magnitude, so it must only ever get darker -- a
    ramp that wrapped back to a light hue would read as a lower dose."""
    for theme in ("light", "dark"):
        for count in (2, 5, 9, 12, 20):
            colors = ramp_colors(count, theme)
            assert len(colors) == count
            luma = [_luma(c) for c in colors]
            assert luma == sorted(luma, reverse=True), f"{theme}/{count} not monotone"
            assert luma[0] > luma[-1], "the ends must be distinguishable"


def test_sweep_grid_legends_each_dose_once(swept):
    timeseries, _ = swept
    fig = sweep_grid(timeseries)
    legended = [trace.name for trace in fig.data if trace.showlegend]
    assert len(legended) == len(set(legended)) == 9
    assert len(fig.data) == 9 * len(SWEEP_PANELS)


def test_dose_response_labels_only_the_final_point(swept):
    _, dose = swept
    fig = dose_response(dose, t_end=600.0)
    labels = [a.text for a in fig.layout.annotations if a.text and "," in a.text]
    assert len(labels) == 1
    assert fig.data[0].marker.size >= 8
