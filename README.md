# Cascade

A two-stage enzymatic signal cascade simulator, translated from `Cascade.m`
into Python with a browser front end.

Analyte **A** binds enzyme **E** to form the complex **EA**, which activates to
**EAact**. That produces the messenger **B**, which drives an identical
bind → activate → produce stage on **F**, yielding the output **C**.

## Running it

```sh
uv sync
uv run streamlit run app.py      # or: uv run main.py
```

The app opens at <http://localhost:8501>.

## Using it

Parameters live in editable tables, one per category, each showing the unit and
a description of every entry:

| Category | Contents |
|---|---|
| Boundary conditions | `A0`, `E0`, `F0` — initial concentrations |
| Kinetic parameters | `k1f` … `k6` — the ten rate constants |
| Time | `t_start`, `t_end`, `n_points` |
| A0 sweep | set `enabled` to 1 to sweep A0 in place of the single dose |

Press **Run simulation** to plot. **Editing any value in any table clears the
plot**, so what is on screen always matches what is in the tables — press Run
again to refresh it.

Give the run a **Name** in the sidebar and press **Save results** to write it to
`results/<name>.toml`. Saved runs can be reloaded from the sidebar, which puts
their parameter set back into the tables.

With the sweep enabled the app reproduces the MATLAB script's `A0 = 0:5:40`
family plus its closing dose-response plot of C at the final time, and adds a
per-dose detail view of every species.

## Saved results

One TOML file per run holds the parameter set *and* the simulated data, so a
result is always self-describing. `[data]` contains nothing but the column
arrays, so it loads with plain pandas and no project code:

```python
import tomllib, pandas as pd

doc = tomllib.load(open("results/baseline.toml", "rb"))
frame = pd.DataFrame(doc["data"])       # time_s + every species
doc["kinetics"], doc["boundary"], doc["units"]   # what produced it
```

Sweeps add a `A0_run` column to `[data]` and a `[dose_response]` table. Column
order is pinned under `[schema]`. Expect ~135 KB for a default single run and
~1.2 MB for the nine-point sweep.

Rates are not stored — they are exactly recoverable from the saved states and
kinetics with `cascade.simulate.rates(frame, params)`, so storing them would
double the file for nothing.

## Layout

| Path | Role |
|---|---|
| `app.py` | Streamlit UI — parameter tables, Run, save/load |
| `cascade/model.py` | the reduced 7-state system, plus the original 9-state reference |
| `cascade/simulate.py` | `solve_ivp` wrappers: single run and A0 sweep |
| `cascade/params.py` | parameter sets, defaults, change fingerprint |
| `cascade/storage.py` | TOML save / load / list |
| `cascade/plots.py` | Plotly figures |
| `cascade/defaults.toml` | starting values, units and descriptions |

## Notes on the translation

- **Seven states are integrated, not nine.** Adding the E, EA and EAact rows of
  the original system cancels every term, so `E + EA + EAact` can never leave
  `E0`; the same holds for `F + FB + FBact` and `F0`. E and F are therefore
  recovered from those balances instead of being integrated, which pins them at
  exactly `E0` and `F0` rather than letting them drift — the residual falls from
  5e-11 to 2e-12 against a tight-tolerance reference. `model.rhs_full` keeps the
  original nine-equation transcription so the tests can check the reduction
  against the system it came from; the two agree to ~1e-8 relative.
- `ode15s` becomes `scipy.integrate.solve_ivp(method="LSODA")`, which likewise
  switches between stiff and non-stiff methods. The system is genuinely stiff:
  A is consumed within milliseconds while C accrues over minutes.
- `Cascade.m` labels all ten rate constants `1/s`, but `k1f` and `k4f` multiply
  a product of two concentrations, so the tables show them as `L/(pmol·s)`. The
  numbers are unchanged.
- The MATLAB 2×2 grid put E (~10⁴ pmol/L) on the same axes as A, EA and EAact
  (~10¹), which flattens three of the four curves onto the baseline. Rows 1–2 of
  the Python grid are 2×3 so every panel spans a single order of magnitude; the
  rows are the two mirrored stages and the columns line up their counterparts.
- Rows 3–4 show the rate of change of every species. Rates are evaluated from
  the model rather than by differencing the solution, so they stay exact through
  the t = 0 binding transient — differencing over the 1 s output step reports
  −20 pmol/L/s there against a true −1155. They span seven orders of magnitude
  and do **not** follow the concentration groupings (`dA/dt` and `dEAact/dt` are
  both stage 1 but differ by 15,000×), so they are grouped strictly by magnitude
  band, which needs two rows. `dE/dt` is dashed because it coincides exactly
  with `dA/dt` — both reduce to `−k1f·A·E + k1b·EA`. The rate axes stay linear
  under the log toggle, since several rates are negative throughout.

## Tests

```sh
uv run pytest
```

Covers the ODE transcription, the state reduction against the original
nine-equation system, solver accuracy against a tight-tolerance reference,
TOML round-tripping, the chart design rules, and the app itself
(driven headlessly through Streamlit's `AppTest`, including the plot-reset
behaviour).
