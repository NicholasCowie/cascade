# Result files

Each saved run is one TOML file in `results/`, named after the run. It holds the
**parameter set and the data together**, so a result is always self-describing —
you never have to remember which settings produced which curve.

## Reading one

`[data]` contains nothing but the column arrays, so the obvious one-liner works
with no project code:

```python
import tomllib, pandas as pd

doc = tomllib.load(open("results/baseline.toml", "rb"))
frame = pd.DataFrame(doc["data"])          # time_s + every species
doc["kinetics"]["k3"]                      # what produced it
doc["units"]["k1f"]                        # "L/(pmol*s)"
```

Or through the package, which also rebuilds the `ParameterSet`:

```python
from cascade.storage import load_run
run = load_run("results/baseline.toml")
run.data          # DataFrame
run.params        # ParameterSet
run.dose_response # DataFrame, or None
```

## Layout

```toml
name = "baseline"
saved_at = "2026-08-19T22:10:36"
schema_version = 1

[solver]
method = "LSODA"
rtol = 1e-08
atol = 1e-10

[boundary]                       # the parameter set exactly as edited
A0 = 20.0
E0 = 35.0
F0 = 40.0

[kinetics]
k1f = 0.0057762265046662105
# ... all ten

[time]
t_start = 0.0
t_end = 600.0
n_points = 601.0

[sweep]
enabled = 0.0
A0_start = 0.0
A0_stop = 40.0
A0_step = 5.0

[units]                          # so the file reads without the app
A0 = "pmol/L"
k1f = "L/(pmol*s)"
# ... every parameter

[schema]                         # column order, kept out of [data]
data = ["time_s", "A", "E", "EA", "EAact", "B", "F", "FB", "FBact", "C"]

[data]                           # arrays only
time_s = [0.0, 1.0, 2.0, ...]
A = [20.0, 0.0, ...]
# ... one array per column
```

### Why `[schema]` is a separate table

Column order was originally stored as a `columns` key *inside* `[data]`. That
broke the headline use case: `pd.DataFrame(doc["data"])` raised
`ValueError: All arrays must be of the same length`, because the 11-element list
of names sat alongside 601-element data arrays.

Keeping `[data]` to arrays alone makes the naive constructor work.
`[schema]` still pins the order explicitly, so a hand-edited or reordered file
still loads its columns in the intended order.
`test_data_section_loads_with_plain_pandas` guards this.

### Sweeps

A swept run adds an `A0_run` column to `[data]` identifying which dose each row
belongs to, and a `[dose_response]` table:

```toml
[schema]
data = ["A0_run", "time_s", "A", ...]
dose_response = ["A0", "C_final"]

[dose_response]
A0 = [0.0, 5.0, 10.0, ...]
C_final = [0.0, 1757.5, 3515.0, ...]
```

## Size

| Run | Rows | File |
|---|---|---|
| Single, 601 points | 601 | ~135 KB |
| Sweep, 9 doses × 601 | 5409 | ~1.2 MB |

TOML stores every number as text, so files are larger than a binary format would
be. Both scale linearly with `n_points` and with the number of swept doses.

## What is not stored

**Rates of change.** They are exactly recoverable from the saved states and rate
constants, so storing them would double the file for nothing:

```python
from cascade.simulate import rates
from cascade.storage import load_run

run = load_run("results/baseline.toml")
rate_frame = rates(run.data, run.params)   # dA_dt ... dC_dt
```

## Notes

- Float values round-trip exactly — `tomli_w` writes full `repr` precision, and
  `test_round_trip_preserves_parameters_and_data` asserts frame equality.
- Run names are sanitised into filenames: `"high dose / run #2"` becomes
  `high-dose-run-2.toml`. Saving over an existing name overwrites it, and the
  sidebar warns first.
- `schema_version` is `1`. Any future change to the layout should raise it.
- A malformed file in `results/` is skipped by the sidebar listing rather than
  breaking it.
