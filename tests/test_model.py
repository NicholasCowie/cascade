"""Checks on the translated ODE system.

The app integrates seven states and recovers E and F from the balances
E + EA + EAact = E0 and F + FB + FBact = F0.  Those balances are consequences
of the nine equations in Cascade.m -- adding the relevant rows of that system
cancels every term -- so the central test here is that the reduced system
reproduces the full one it was derived from.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from cascade.model import (
    DERIVED,
    SPECIES,
    STATE,
    expand,
    expand_rates,
    free_enzymes,
    initial_state,
    initial_state_full,
    rhs,
    rhs_full,
)
from cascade.params import load_defaults
from cascade.simulate import SolverSettings, integrate, rates, run_single, run_sweep


@pytest.fixture
def params():
    return load_defaults()[0]


def test_state_layout():
    assert set(STATE) | set(DERIVED) == set(SPECIES)
    assert not set(STATE) & set(DERIVED)
    assert len(STATE) == 7 and len(DERIVED) == 2


def test_full_system_rows_cancel_for_each_balance():
    """Why E and F can be eliminated at all: the sums are identically zero for
    any state and any rate constants, not just at the default values."""
    rng = np.random.default_rng(0)
    for _ in range(50):
        x = rng.uniform(0.0, 1000.0, size=len(SPECIES))
        k = rng.uniform(0.0, 0.5, size=10)
        dA, dE, dEA, dEAact, _, dF, dFB, dFBact, _ = rhs_full(0.0, x, k)
        assert dE + dEA + dEAact == pytest.approx(0.0, abs=1e-9)
        assert dF + dFB + dFBact == pytest.approx(0.0, abs=1e-9)
        assert dA + dEA + dEAact == pytest.approx(0.0, abs=1e-9)


def test_reduced_rhs_matches_the_full_rhs():
    """Point-for-point agreement of the two right-hand sides."""
    rng = np.random.default_rng(1)
    for _ in range(50):
        state = rng.uniform(0.0, 50.0, size=7)
        E0, F0 = 10000.0, 10000.0
        k = rng.uniform(0.0, 0.5, size=10)

        full_state = expand(state, E0, F0)[0]
        expected = rhs_full(0.0, full_state, k)
        produced = expand_rates(rhs(0.0, state, k, E0, F0))[0]
        assert produced == pytest.approx(expected, rel=1e-12, abs=1e-12)


def test_reduced_solution_matches_the_original_nine_state_system(params):
    """The reduction must not change the answer, only how it is obtained."""
    reduced = run_single(params)
    grid = reduced["time_s"].to_numpy()

    reference = solve_ivp(
        rhs_full,
        (grid[0], grid[-1]),
        initial_state_full(*(params.boundary[n] for n in ("A0", "E0", "F0"))),
        t_eval=grid,
        args=(params.k,),
        method="Radau",
        rtol=1e-12,
        atol=1e-14,
    )
    assert reference.success

    for index, species in enumerate(SPECIES):
        scale = max(np.abs(reference.y[index]).max(), 1.0)
        assert reduced[species].to_numpy() == pytest.approx(
            reference.y[index], abs=1e-6 * scale
        ), species


def test_balances_hold_to_floating_point(params):
    """E and F come from the balances, so they cannot drift the way an
    integrated state can."""
    frame = run_single(params)

    def total(*names):
        return sum(frame[name].to_numpy() for name in names)

    assert total("E", "EA", "EAact") == pytest.approx(params.boundary["E0"], abs=1e-9)
    assert total("F", "FB", "FBact") == pytest.approx(params.boundary["F0"], abs=1e-9)
    # A stays an integrated state, so it is held only to solver tolerance.
    assert total("A", "EA", "EAact") == pytest.approx(params.boundary["A0"], abs=1e-6)


def test_free_enzymes_invert_the_state(params):
    frame = run_single(params)
    state = frame[list(STATE)].to_numpy()
    for row, (E, F) in zip(frame.itertuples(index=False), map(
        lambda x: free_enzymes(x, params.boundary["E0"], params.boundary["F0"]), state
    )):
        assert E == pytest.approx(row.E)
        assert F == pytest.approx(row.F)


def test_zero_dose_produces_no_output(params):
    frame = integrate(params, A0=0.0)
    for species in ("EA", "EAact", "B", "FB", "FBact", "C"):
        assert frame[species].abs().max() == pytest.approx(0.0, abs=1e-12)
    assert frame["E"].to_numpy() == pytest.approx(params.boundary["E0"])
    assert frame["F"].to_numpy() == pytest.approx(params.boundary["F0"])


def test_output_accumulates_monotonically(params):
    """dC/dt = k6*FBact with k6 > 0 and FBact >= 0, so C never decreases."""
    frame = run_single(params)
    assert np.all(np.diff(frame["C"].to_numpy()) >= -1e-9)
    assert frame["C"].iloc[-1] > 0.0


def test_matlab_initial_state_layout():
    assert list(initial_state(20.0)) == [20.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert list(initial_state_full(20.0, 10000.0, 10000.0)) == [
        20.0, 10000.0, 0.0, 0.0, 0.0, 10000.0, 0.0, 0.0, 0.0
    ]


def test_lsoda_agrees_with_a_stiff_reference(params):
    """LSODA stands in for ode15s; check it against tight-tolerance Radau."""
    reference = run_single(params, solver=SolverSettings("Radau", rtol=1e-11, atol=1e-13))
    trial = run_single(params)
    for species in SPECIES:
        scale = max(reference[species].abs().max(), 1.0)
        assert np.allclose(trial[species], reference[species], atol=1e-6 * scale)


def test_dose_response_increases_with_A0(params):
    timeseries, dose = run_sweep(params)
    assert list(dose["A0"]) == [0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0]
    assert np.all(np.diff(dose["C_final"].to_numpy()) > 0.0)
    assert dose["C_final"].iloc[0] == pytest.approx(0.0, abs=1e-12)
    assert len(timeseries) == len(dose) * int(params.time["n_points"])


def test_time_grid_is_validated(params):
    bad = params.with_category("time", {**params.time, "t_end": 0.0})
    with pytest.raises(ValueError, match="t_end"):
        run_single(bad)

    bad = params.with_category("time", {**params.time, "n_points": 1.0})
    with pytest.raises(ValueError, match="n_points"):
        run_single(bad)


# --- rates -------------------------------------------------------------------


def test_rates_are_exact_not_differenced(params):
    """Rates come from the model, so they are right even where the solution is
    sampled far too coarsely to difference -- as at t = 0, where the binding
    transient decays within a fraction of the 1 s output step."""
    frame = run_single(params)
    rate = rates(frame, params)

    assert list(rate.columns) == ["time_s"] + [f"d{s}_dt" for s in SPECIES]
    assert rate["dA_dt"].iloc[0] == pytest.approx(
        -params.kinetics["k1f"] * params.boundary["A0"] * params.boundary["E0"]
    )

    # In the interior, where central differencing is second-order accurate,
    # the two agree closely.  They cannot agree at t=0, where the transient
    # decays well inside one output step, nor at the endpoints, where
    # np.gradient falls back to a one-sided difference.
    differenced = np.gradient(frame["C"].to_numpy(), frame["time_s"].to_numpy())
    interior = slice(10, -1)
    assert rate["dC_dt"].to_numpy()[interior] == pytest.approx(
        differenced[interior], abs=1e-3
    )
    # Exactness is the real property: every value equals the model evaluated
    # at that state, to machine precision.
    state = frame[list(STATE)].to_numpy()
    direct = expand_rates(
        np.array(
            [
                rhs(t, x, params.k, params.boundary["E0"], params.boundary["F0"])
                for t, x in zip(frame["time_s"], state)
            ]
        )
    )
    for index, species in enumerate(SPECIES):
        assert rate[f"d{species}_dt"].to_numpy() == pytest.approx(
            direct[:, index], abs=0.0, rel=0.0
        ), species


def test_differencing_would_flatten_a_stiff_transient():
    """Why rates are evaluated rather than differenced.

    How wrong differencing is depends on the regime.  At the project defaults
    the enzymes are scarce and the transient is mild, so it barely matters --
    but raise E0 to the 10000 pmol/L of Cascade.m and binding finishes far
    inside one output step, where differencing understates the initial rate by
    almost two orders of magnitude.
    """
    params = load_defaults()[0]
    stiff = params.with_category(
        "boundary", {**params.boundary, "E0": 10000.0, "F0": 10000.0}
    )

    frame = run_single(stiff)
    exact = rates(frame, stiff)["dA_dt"].iloc[0]
    differenced = np.gradient(frame["A"].to_numpy(), frame["time_s"].to_numpy())[0]

    assert exact == pytest.approx(-1155.2, rel=1e-3)
    assert abs(exact) > 50 * abs(differenced)


def test_derived_rates_match_the_balances(params):
    frame = run_single(params)
    rate = rates(frame, params)

    assert rate["dE_dt"].to_numpy() == pytest.approx(
        -(rate["dEA_dt"] + rate["dEAact_dt"]).to_numpy(), abs=1e-15
    )
    assert rate["dF_dt"].to_numpy() == pytest.approx(
        -(rate["dFB_dt"] + rate["dFBact_dt"]).to_numpy(), abs=1e-15
    )
    # dA/dt and dE/dt reduce to the same expression, which is why the figure
    # dashes one of them.
    assert rate["dA_dt"].to_numpy() == pytest.approx(rate["dE_dt"].to_numpy(), abs=1e-15)


def test_rates_carry_the_sweep_column(params):
    timeseries, _ = run_sweep(params)
    rate = rates(timeseries, params)
    assert rate.columns[0] == "A0_run"
    assert rate["A0_run"].nunique() == 9
    assert len(rate) == len(timeseries)
