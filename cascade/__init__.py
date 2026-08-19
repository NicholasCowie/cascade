"""Two-stage enzymatic signal cascade, translated from Cascade.m.

The public API, by module:

``model``
    The equations.  ``rhs`` is the seven-state system the app integrates;
    ``rhs_full`` is the original nine-equation transcription, kept as a
    reference to check the reduction against.  ``expand`` and ``expand_rates``
    recover E and F -- and their rates -- from the conservation balances.

``simulate``
    ``run_single`` and ``run_sweep`` integrate and return pandas DataFrames;
    ``rates`` evaluates every species' rate of change exactly, from the model
    rather than by differencing the solution.

``params``
    ``ParameterSet`` plus ``load_defaults``, which reads values, units and
    descriptions from ``defaults.toml``.

``storage``
    Reading and writing runs as self-describing TOML files.

See ``docs/model.md`` for the equations and the derivation of the reduction.
"""

from .model import (
    DERIVED,
    PARAM_ORDER,
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
from .params import ParameterSet, load_defaults, units_flat
from .simulate import (
    RATE_COLUMNS,
    SimulationError,
    SolverSettings,
    integrate,
    rate_column,
    rates,
    run_single,
    run_sweep,
)
from .storage import list_runs, load_run, save_run

__all__ = [
    # model
    "DERIVED",
    "PARAM_ORDER",
    "SPECIES",
    "STATE",
    "expand",
    "expand_rates",
    "free_enzymes",
    "initial_state",
    "initial_state_full",
    "rhs",
    "rhs_full",
    # params
    "ParameterSet",
    "load_defaults",
    "units_flat",
    # simulate
    "RATE_COLUMNS",
    "SimulationError",
    "SolverSettings",
    "integrate",
    "rate_column",
    "rates",
    "run_single",
    "run_sweep",
    # storage
    "list_runs",
    "load_run",
    "save_run",
]
