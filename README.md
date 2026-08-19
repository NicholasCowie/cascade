# Cascade

A two-stage enzymatic signal cascade simulator, translated from `Cascade.m` into
Python with a browser front end.

Analyte **A** binds enzyme **E** to form the complex **EA**, which activates to
**EAact**. That produces the messenger **B**, which drives an identical
bind → activate → produce stage on **F**, yielding the output **C**.

Parameters are edited in tables with their units shown, a Run button plots the
result, and each saved run is a single self-describing file holding the data and
the settings that produced it.

## Running it

From a source checkout:

```sh
uv sync
uv run streamlit run app.py      # or: uv run main.py
```

The app opens at <http://localhost:8501>.

As a standalone build, for a machine with no Python — see
[docs/packaging.md](docs/packaging.md) to produce one and [USING.md](USING.md)
for the guide aimed at whoever receives it:

```sh
uv run pyinstaller cascade.spec --noconfirm
cd dist/cascade && ./cascade --selftest && ./cascade
```

## Using it

Four editable tables, each showing the unit and description of every entry:

| Category | Contents |
|---|---|
| Boundary conditions | `A0`, `E0`, `F0` — initial concentrations |
| Kinetic parameters | `k1f` … `k6` — the ten rate constants |
| Time | `t_start`, `t_end`, `n_points` |
| A0 sweep | set `enabled` to 1 to sweep A0 in place of the single dose |

Press **Run simulation** to plot. **Editing any value in any table clears the
plot**, so what is on screen always matches what is in the tables — press Run
again to refresh it.

Name a run in the sidebar and press **Save results** to write it to
`results/<name>.toml`. Saved runs reload from the sidebar, putting their
parameter set back into the tables.

With the sweep enabled the app reproduces the MATLAB script's `A0 = 0:5:40`
family and its dose-response plot of C at the final time, and adds a per-dose
detail view.

### The plots

A 4×3 grid. Rows 1–2 are concentrations, one magnitude band per panel, with the
two stages mirroring each other:

| | Complexes | Free enzyme | Stage output |
|---|---|---|---|
| **Stage 1** | A, EA, EAact | E | B |
| **Stage 2** | FB, FBact | F | C |

Rows 3–4 are rates of change, grouped strictly by magnitude, because they do not
follow the concentration groupings. A sweep adds its own overlay figure plus the
dose-response curve.

## Documentation

| | |
|---|---|
| [USING.md](USING.md) | Plain-language guide for running a downloaded build |
| [docs/model.md](docs/model.md) | The equations, the state reduction, the defaults |
| [docs/file-format.md](docs/file-format.md) | Result file layout, reading it with pandas |
| [docs/packaging.md](docs/packaging.md) | Building the executable, and the gotchas |

## Saved results

One TOML file per run, holding the parameter set *and* the data. `[data]`
contains nothing but column arrays, so it loads with plain pandas and no project
code:

```python
import tomllib, pandas as pd

doc = tomllib.load(open("results/baseline.toml", "rb"))
frame = pd.DataFrame(doc["data"])                # time_s + every species
doc["kinetics"], doc["boundary"], doc["units"]   # what produced it
```

Rates are not stored — `cascade.simulate.rates` recovers them exactly. Full
layout in [docs/file-format.md](docs/file-format.md).

## Layout

| Path | Role |
|---|---|
| `app.py` | Streamlit UI — parameter tables, Run, save/load |
| `launcher.py` | entry point for the packaged build |
| `cascade/model.py` | the equations: 7-state system plus the 9-state reference |
| `cascade/simulate.py` | `solve_ivp` wrappers, and exact rates |
| `cascade/params.py` | parameter sets, defaults, change fingerprint |
| `cascade/storage.py` | TOML save / load / list |
| `cascade/plots.py` | Plotly figures |
| `cascade/paths.py` | source-tree vs. PyInstaller-bundle paths |
| `cascade/defaults.toml` | starting values, units and descriptions |
| `cascade.spec` | PyInstaller build definition |

## Notes on the translation

- **Seven states are integrated, not nine.** `E + EA + EAact` can never leave
  `E0`, and `F + FB + FBact` can never leave `F0` — both follow identically from
  the original equations — so E and F are recovered from those balances rather
  than integrated. Their residual drops to 7e-15, one bit of double precision,
  and the two systems agree to ~1e-8 relative. Derivation in
  [docs/model.md](docs/model.md).
- **The enzymes start at 35 and 40 pM, not the 10000 pmol/L of `Cascade.m`.**
  Comparable to the 20 pM dose rather than in 500-fold excess, so they are
  limiting: F is fully consumed by t ≈ 150 s, B accumulates instead of being
  turned over, and the dose response saturates rather than running linear.
- `ode15s` becomes `solve_ivp(method="LSODA")`, which likewise switches between
  stiff and non-stiff methods. Stiffness depends on those enzyme levels — mild
  at the defaults, severe at `Cascade.m`'s, where binding completes in
  milliseconds while C accrues over minutes.
- `Cascade.m:4` labels all ten rate constants `1/s`, but `k1f` and `k4f`
  multiply two concentrations, so the tables show `L/(pmol·s)`. The numbers are
  unchanged.
- The MATLAB 2×2 grid put E on the same axes as A, EA and EAact — safe only
  while they are the same size, and at `Cascade.m`'s `E0` it flattens three
  curves onto the baseline. Every panel now spans a single order of magnitude,
  whatever the enzyme concentrations.
- Rates are evaluated from the model, not by differencing the solution, so they
  stay exact however coarse the output grid. Differencing goes badly wrong for
  any transient faster than one output step: at `E0 = 10000` it reports
  −20 pmol/L/s against a true −1155.

## Tests

```sh
uv run pytest
```

85 tests covering the ODE transcription, the state reduction against the
original nine-equation system, solver accuracy against a tight-tolerance
reference, TOML round-tripping, the chart design rules, frozen-build path
resolution, and the app itself — driven headlessly through Streamlit's
`AppTest`, including the plot-reset behaviour.
