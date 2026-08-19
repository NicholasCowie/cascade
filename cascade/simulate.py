"""Integrating the cascade: single runs and A0 sweeps."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp

from .model import (
    SPECIES,
    STATE,
    expand,
    expand_rates,
    initial_state,
    rhs,
)
from .params import ParameterSet

TIME_COLUMN = "time_s"
SWEEP_COLUMN = "A0_run"


def rate_column(species: str) -> str:
    return f"d{species}_dt"


RATE_COLUMNS: tuple[str, ...] = tuple(rate_column(name) for name in SPECIES)


@dataclass(frozen=True)
class SolverSettings:
    """LSODA is the closest analogue to MATLAB's ode15s: it switches between
    stiff and non-stiff methods internally, which this system needs -- with the
    default rates, A is consumed within milliseconds while C accrues over
    minutes."""

    method: str = "LSODA"
    rtol: float = 1e-8
    atol: float = 1e-10

    def to_dict(self) -> dict[str, float | str]:
        return {"method": self.method, "rtol": self.rtol, "atol": self.atol}


class SimulationError(RuntimeError):
    """Raised when the integrator fails, rather than plotting a partial run."""


def _time_grid(params: ParameterSet) -> np.ndarray:
    t_start = float(params.time["t_start"])
    t_end = float(params.time["t_end"])
    n_points = int(round(float(params.time["n_points"])))

    if t_end <= t_start:
        raise ValueError("t_end must be greater than t_start.")
    if n_points < 2:
        raise ValueError("n_points must be at least 2.")

    return np.linspace(t_start, t_end, n_points)


def integrate(
    params: ParameterSet,
    A0: float | None = None,
    solver: SolverSettings | None = None,
) -> pd.DataFrame:
    """Integrate one trajectory and return time plus every species."""
    solver = solver or SolverSettings()
    t_eval = _time_grid(params)
    k = params.k
    E0 = float(params.boundary["E0"])
    F0 = float(params.boundary["F0"])

    x0 = initial_state(A0 if A0 is not None else float(params.boundary["A0"]))

    sol = solve_ivp(
        rhs,
        (t_eval[0], t_eval[-1]),
        x0,
        t_eval=t_eval,
        args=(k, E0, F0),
        method=solver.method,
        rtol=solver.rtol,
        atol=solver.atol,
    )
    if not sol.success:
        raise SimulationError(f"Integration failed: {sol.message}")

    # Seven states are integrated; E and F come back from their balances.
    frame = pd.DataFrame(expand(sol.y.T, E0, F0), columns=list(SPECIES))
    frame.insert(0, TIME_COLUMN, sol.t)
    return frame


def run_single(
    params: ParameterSet, solver: SolverSettings | None = None
) -> pd.DataFrame:
    """One trajectory at the A0 given in the boundary conditions."""
    return integrate(params, solver=solver)


def run_sweep(
    params: ParameterSet, solver: SolverSettings | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sweep A0, as Cascade.m does over 0:5:40.

    Returns the stacked time courses (with an ``A0_run`` column identifying
    each) and the dose response of C at the final time against A0.
    """
    frames: list[pd.DataFrame] = []
    dose: list[dict[str, float]] = []

    for A0 in params.sweep_values():
        frame = integrate(params, A0=A0, solver=solver)
        frame.insert(0, SWEEP_COLUMN, A0)
        frames.append(frame)
        dose.append({"A0": A0, "C_final": float(frame["C"].iloc[-1])})

    return pd.concat(frames, ignore_index=True), pd.DataFrame(dose)


def rates(frame: pd.DataFrame, params: ParameterSet) -> pd.DataFrame:
    """Rate of change of every species at each stored timepoint.

    Evaluated from the model itself rather than by differencing the solution,
    so the result is exact at every point instead of an approximation that
    smears the sub-second binding transient at t = 0.
    """
    k = params.k
    E0 = float(params.boundary["E0"])
    F0 = float(params.boundary["F0"])
    states = frame[list(STATE)].to_numpy()
    times = frame[TIME_COLUMN].to_numpy()

    derivatives = np.array([rhs(t, x, k, E0, F0) for t, x in zip(times, states)])
    result = pd.DataFrame(
        expand_rates(derivatives), columns=list(RATE_COLUMNS), index=frame.index
    )
    result.insert(0, TIME_COLUMN, times)
    if SWEEP_COLUMN in frame.columns:
        result.insert(0, SWEEP_COLUMN, frame[SWEEP_COLUMN].to_numpy())
    return result
