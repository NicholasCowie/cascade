"""Cascade simulator -- browser front end.

Run with:  uv run streamlit run app.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from cascade.params import (
    CATEGORIES,
    CATEGORY_LABELS,
    ParameterSet,
    load_defaults,
    units_flat,
)
from cascade.plots import dose_response, sweep_grid, timecourse_grid
from cascade.simulate import (
    SWEEP_COLUMN,
    SolverSettings,
    rates,
    run_single,
    run_sweep,
)
from cascade.storage import list_runs, load_run, run_path, save_run

CONC_UNIT = "pmol/L"
TIME_UNIT = "s"

RATE_CAPTION = (
    "Rows 3–4 are rates of change, grouped by magnitude — they span seven "
    "orders, so they do not follow the concentration groupings above. "
    "dE/dt is dashed because it coincides exactly with dA/dt: both reduce to "
    "−k1f·A·E + k1b·EA. Rate axes stay linear, since several rates are negative."
)

st.set_page_config(page_title="Cascade simulator", page_icon="🧪", layout="wide")


# --- state -------------------------------------------------------------------


def _init_state() -> None:
    if "params" not in st.session_state:
        params, metadata = load_defaults()
        st.session_state.params = params
        st.session_state.metadata = metadata
        st.session_state.results = None
        st.session_state.results_fp = None
        st.session_state.generation = 0
        st.session_state.run_name = "baseline"


def _load_into_state(params: ParameterSet) -> None:
    """Replace the parameters and force the editors to rebuild."""
    st.session_state.params = params
    st.session_state.results = None
    st.session_state.results_fp = None
    st.session_state.generation += 1


_init_state()
metadata = st.session_state.metadata


# --- parameter tables --------------------------------------------------------


def parameter_editor(category: str, params: ParameterSet) -> dict[str, float]:
    """One editable table: Parameter | Value | Unit | Description."""
    values = params.category(category)
    meta = metadata[category]

    frame = pd.DataFrame(
        {
            "Parameter": list(values),
            "Value": [float(v) for v in values.values()],
            "Unit": [meta[k]["unit"] for k in values],
            "Description": [meta[k]["description"] for k in values],
        }
    )

    edited = st.data_editor(
        frame,
        key=f"editor_{category}_{st.session_state.generation}",
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        disabled=["Parameter", "Unit", "Description"],
        column_config={
            "Value": st.column_config.NumberColumn(
                "Value", format="%.6g", required=True
            ),
            "Description": st.column_config.TextColumn("Description", width="large"),
        },
    )
    return {
        str(row.Parameter): float(row.Value) for row in edited.itertuples(index=False)
    }


st.title("Enzymatic cascade simulator")
st.caption(
    "A → E → EA → EAact → B → F → FB → FBact → C. "
    "Translated from `Cascade.m`; edit any parameter and press Run."
)

left, right = st.columns([1, 1], gap="large")

with left:
    st.subheader(CATEGORY_LABELS["boundary"])
    boundary = parameter_editor("boundary", st.session_state.params)

    st.subheader(CATEGORY_LABELS["time"])
    time_values = parameter_editor("time", st.session_state.params)

    st.subheader(CATEGORY_LABELS["sweep"])
    st.caption(
        "Set `enabled` to 1 to sweep A0 in place of the single dose above, "
        "reproducing the `A0 = 0:5:40` sweep in the MATLAB script."
    )
    sweep = parameter_editor("sweep", st.session_state.params)

with right:
    st.subheader(CATEGORY_LABELS["kinetics"])
    st.caption(
        "k1f and k4f act on a product of two concentrations, so they carry "
        "L/(pmol·s); the other eight are 1/s."
    )
    kinetics = parameter_editor("kinetics", st.session_state.params)

params = ParameterSet(
    boundary=boundary, kinetics=kinetics, time=time_values, sweep=sweep
)
st.session_state.params = params
fingerprint = params.fingerprint()


# --- sidebar -----------------------------------------------------------------

with st.sidebar:
    st.header("Results")
    st.session_state.run_name = st.text_input(
        "Name", value=st.session_state.run_name, help="Used as the filename stem."
    )

    results = st.session_state.results
    target = run_path(st.session_state.run_name)
    if target.exists():
        st.caption(f"⚠️ `{target.name}` exists and will be overwritten.")

    if st.button(
        "Save results",
        width="stretch",
        disabled=results is None,
        help="Writes the parameter set and the simulated data to one TOML file.",
    ):
        path = save_run(
            name=st.session_state.run_name,
            params=results["params"],
            data=results["data"],
            units=units_flat(metadata),
            solver=results["solver"],
            dose_response=results.get("dose"),
        )
        st.success(f"Saved `{path.name}` ({path.stat().st_size / 1024:,.0f} KB)")

    st.divider()
    st.header("Load")
    saved = list_runs()
    if saved:
        labels = {
            f"{item['name']} · {item['saved_at'][:16]}": item["path"] for item in saved
        }
        choice = st.selectbox("Saved run", list(labels), label_visibility="collapsed")
        if st.button("Load parameters", width="stretch"):
            _load_into_state(load_run(labels[choice]).params)
            st.rerun()
    else:
        st.caption("No saved runs yet.")

    if st.button("Reset to defaults", width="stretch"):
        _load_into_state(load_defaults()[0])
        st.rerun()

    st.divider()
    st.header("Solver")
    method = st.selectbox(
        "Method",
        ["LSODA", "BDF", "Radau", "RK45"],
        help="LSODA is the closest analogue to MATLAB's ode15s.",
    )
    rtol = st.select_slider(
        "Relative tolerance", [1e-6, 1e-7, 1e-8, 1e-9, 1e-10], value=1e-8
    )
    solver = SolverSettings(method=method, rtol=rtol, atol=rtol * 1e-2)

    st.divider()
    theme_choice = st.radio("Chart theme", ["Auto", "Light", "Dark"], horizontal=True)
    y_type = st.radio(
        "Y axis",
        ["linear", "log"],
        horizontal=True,
        help="Log reveals the low-abundance species alongside the enzymes.",
    )

if theme_choice == "Auto":
    try:
        theme = st.context.theme.type or "light"
    except Exception:  # older Streamlit without st.context.theme
        theme = "light"
else:
    theme = theme_choice.lower()


# --- run ---------------------------------------------------------------------

st.divider()
run_clicked = st.button("▶  Run simulation", type="primary", width="stretch")

if run_clicked:
    try:
        if params.sweep_enabled:
            data, dose = run_sweep(params, solver=solver)
        else:
            data, dose = run_single(params, solver=solver), None
    except Exception as error:  # surfaced rather than leaving a stale plot
        st.error(f"Simulation failed: {error}")
    else:
        st.session_state.results = {
            "data": data,
            "rates": rates(data, params),
            "dose": dose,
            "params": params,
            "solver": solver.to_dict(),
        }
        st.session_state.results_fp = fingerprint

# Any edit to any table changes the fingerprint, so a stale plot never survives
# a parameter change.
if (
    st.session_state.results is not None
    and st.session_state.results_fp != fingerprint
):
    st.session_state.results = None
    st.session_state.results_fp = None

results = st.session_state.results

if results is None:
    st.info("Parameters changed — press **Run simulation** to plot.")
else:
    data = results["data"]
    dose = results.get("dose")
    swept = dose is not None

    if swept:
        st.plotly_chart(
            sweep_grid(data, theme=theme, y_type=y_type, conc_unit=CONC_UNIT,
                       time_unit=TIME_UNIT),
            width="stretch",
        )
        st.caption(
            "Darker curves are higher A0. Colour carries dose magnitude; "
            "each curve is named in the legend and on hover."
        )
        st.plotly_chart(
            dose_response(dose, t_end=float(params.time["t_end"]), theme=theme,
                          conc_unit=CONC_UNIT, time_unit=TIME_UNIT),
            width="stretch",
        )

        doses = sorted(data[SWEEP_COLUMN].unique())
        detail = st.selectbox(
            "Full species detail for A0 =", doses, index=len(doses) - 1,
            format_func=lambda v: f"{v:g} {CONC_UNIT}",
        )
        chosen = data[SWEEP_COLUMN] == detail
        st.plotly_chart(
            timecourse_grid(
                data[chosen], results["rates"][chosen], theme=theme, y_type=y_type,
                conc_unit=CONC_UNIT, time_unit=TIME_UNIT,
            ),
            width="stretch",
        )
        st.caption(RATE_CAPTION)
    else:
        st.plotly_chart(
            timecourse_grid(data, results["rates"], theme=theme, y_type=y_type,
                            conc_unit=CONC_UNIT, time_unit=TIME_UNIT),
            width="stretch",
        )
        st.caption(RATE_CAPTION)

    # The table view is the relief for the light-mode series that sit below
    # 3:1 on the light surface, and doubles as the numeric readout.
    with st.expander("Data table"):
        concentrations, rate_table = st.tabs(["Concentrations", "Rates of change"])
        with concentrations:
            st.dataframe(data, width="stretch", height=320)
        with rate_table:
            st.dataframe(results["rates"], width="stretch", height=320)
        if swept:
            st.dataframe(dose, width="stretch")
