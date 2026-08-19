# The model

A two-stage enzymatic signal cascade, translated from `Cascade.m`.

Analyte **A** binds enzyme **E** to form the complex **EA**, which activates to
**EAact**. The activated complex produces the messenger **B**, which drives an
identical bind → activate → produce stage on **F**, yielding the output **C**.

```
        k1f          k2f          k3
  A + E ---> EA  --------> EAact ----> B          (stage 1)
        k1b          k2b

        k4f          k5f          k6
  B + F ---> FB  --------> FBact ----> C          (stage 2)
        k4b          k5b
```

## The equations

The nine species are `A, E, EA, EAact, B, F, FB, FBact, C`. `Cascade.m:17-25`
gives one differential equation for each:

```
dA/dt     = -k1f·A·E + k1b·EA
dE/dt     = -k1f·A·E + k1b·EA
dEA/dt    =  k1f·A·E - k1b·EA - k2f·EA + k2b·EAact
dEAact/dt =  k2f·EA - k2b·EAact
dB/dt     =  k3·EAact - k4f·B·F + k4b·FB
dF/dt     = -k4f·B·F + k4b·FB
dFB/dt    =  k4f·B·F - k4b·FB - k5f·FB + k5b·FBact
dFBact/dt =  k5f·FB - k5b·FBact
dC/dt     =  k6·FBact
```

This system is `model.rhs_full`. Nothing in the app uses it; it is kept so the
tests can check the reduction below against the system it came from.

## The conservation balances

Add the E, EA and EAact rows:

```
dE/dt + dEA/dt + dEAact/dt
  = (-k1f·A·E + k1b·EA)
  + ( k1f·A·E - k1b·EA - k2f·EA + k2b·EAact)
  + ( k2f·EA - k2b·EAact)
  = 0
```

Every term cancels. This holds **identically** — for any state and any values
of the ten rate constants, not merely at the defaults — so

```
E + EA + EAact = E₀        for all t
```

The same cancellation on the F, FB and FBact rows gives `F + FB + FBact = F₀`.

These are consequences of the equations, not extra constraints imposed on them.
`tests/test_model.py::test_full_system_rows_cancel_for_each_balance` checks the
cancellation directly on `rhs_full`, over random states and random rate
constants, which is what licenses eliminating anything at all.

## The reduced system

Since E and F are fixed by the balances, they need not be integrated.
`model.rhs` integrates **seven** states — `A, EA, EAact, B, FB, FBact, C` —
and recovers the other two algebraically at each evaluation:

```
E = E₀ - EA - EAact
F = F₀ - FB - FBact
```

`model.expand` applies this to a whole solution, turning the `(n, 7)` integrated
result into the `(n, 9)` table the app reports. `model.expand_rates` does the
same for rates, differentiating the balances:

```
dE/dt = -(dEA/dt + dEAact/dt)
dF/dt = -(dFB/dt + dFBact/dt)
```

### What it buys

E and F can no longer drift, because nothing integrates them. Measured against
a tight-tolerance `Radau` reference:

| Quantity (at the defaults) | Nine integrated states | Seven states + balances |
|---|---|---|
| `F + FB + FBact` residual | 1.1 × 10⁻¹³ | 7.1 × 10⁻¹⁵ |
| `E + EA + EAact` residual | 1.1 × 10⁻¹³ | 7.1 × 10⁻¹⁵ |

7.1 × 10⁻¹⁵ on a value of 40 is one bit of double precision — the rounding in
`F0 - FB - FBact` itself, and the floor for this representation. The margin is
wider the harder the problem: at `Cascade.m`'s `E0 = F0 = 10000` the integrated
system drifts to 5.5 × 10⁻¹¹ against 1.8 × 10⁻¹² for the balances.

The two systems agree to ~10⁻⁸ relative on every species
(`test_reduced_solution_matches_the_original_nine_state_system`), so the
reduction changes how the answer is obtained, not what it is.

### A is eliminable too

`dA/dt` and `dE/dt` are the same expression, so `A - E` is constant and

```
A + EA + EAact = A₀
```

holds by exactly the same argument. `A` is nonetheless still integrated — the
reduction was deliberately scoped to two states. Its balance therefore holds
only to solver tolerance (~10⁻¹³) rather than exactly, which is why the test for
it uses a looser bound than the E and F ones.

The identity has one visible consequence: `dA/dt` and `dE/dt` coincide for every
parameter value, so in the rate panels one of them is dashed — otherwise the
second curve would be drawn exactly on top of the first and appear to be
missing.

## Default parameters

Editable in [`cascade/defaults.toml`](../cascade/defaults.toml). The rate
constants, time grid and sweep are `Cascade.m`'s, unchanged; **the enzyme
concentrations are not** — see below.

| Parameter | Value | Unit | Meaning |
|---|---|---|---|
| `A0` | 20 | pM | initial analyte |
| `E0` | 35 | pM | initial enzyme E |
| `F0` | 40 | pM | initial enzyme F |
| `k1f`, `k4f` | ln2/120 ≈ 5.776×10⁻³ | L/(pmol·s) | association |
| `k2f`, `k5f` | ln2/180 ≈ 3.851×10⁻³ | 1/s | activation |
| `k3`, `k6` | 0.1 | 1/s | production |
| `k1b`, `k2b`, `k4b`, `k5b` | 0 | 1/s | reverse steps |
| time | 0 … 600, 601 points | s | |
| sweep | A0 = 0 : 5 : 40 | pM | |

(pM and pmol/L are the same unit. The tables display `pmol/L`.)

**Units correction.** `Cascade.m:4` labels all ten rate constants `1/s`. But
`k1f` and `k4f` multiply a *product of two concentrations*, so dimensional
consistency requires `L/(pmol·s)`; the other eight are `1/s`. The app displays
the corrected units. **The rate values are unchanged.**

### The enzyme concentrations change the regime

`Cascade.m` starts both enzymes at 10000 pmol/L against a 20 pmol/L dose — a
500-fold excess, so the enzymes are effectively constant and every step is
pseudo-first-order in the analyte. The defaults here put them at 35 and 40 pM,
*comparable to the dose*, which makes them limiting and changes the behaviour
qualitatively:

| | `E0 = F0 = 10000` (Cascade.m) | `E0 = 35`, `F0 = 40` (default) |
|---|---|---|
| C at 600 s | 7030 pM (352× amplification) | 1156 pM (58×) |
| Messenger B | 0.034 pM — consumed as fast as made | 679 pM — accumulates |
| Free F at 600 s | 9268 pM, barely touched | 0 — fully consumed by t ≈ 150 s |
| Dose response | near-linear in A0 | saturating |
| Initial `dA/dt` | −1155 pM/s | −4.04 pM/s |

The saturation is the point of interest: once F is exhausted the second stage
cannot turn any more B into C, so B piles up and C plateaus. Doubling the dose
from 20 to 40 pM raises C at 600 s only from 1156 to 1217 pM.

## Integration

`ode15s` becomes `scipy.integrate.solve_ivp(method="LSODA")`, which likewise
switches between stiff and non-stiff methods internally.

How stiff the system is depends on those enzyme concentrations. At the defaults
it is mild — `k1f·A·E ≈ 4.04 pM/s` at t = 0, and A takes about 5 s to halve. At
`Cascade.m`'s `E0 = 10000` the same expression is 1155 pM/s and binding finishes
within milliseconds while C accrues over minutes, so the solver must span both
timescales. LSODA handles either without configuration.

Defaults are `rtol=1e-8`, `atol=1e-10`; the app exposes the method and tolerance
in the sidebar. `test_lsoda_agrees_with_a_stiff_reference` pins LSODA against
tight-tolerance `Radau`.

## Rates of change

`simulate.rates` evaluates `rhs` at each stored timepoint rather than
differencing the solution, so every value is exact rather than an approximation
whose error depends on the output spacing.

At the defaults, differencing would be a fair approximation. It stops being one
as soon as a transient is faster than the output step: at `E0 = 10000` the true
`dA/dt` at t = 0 is −1155 pM/s, while differencing over the 1 s step reports
−20 — an understatement of 58×, because A is gone long before the next sample.
`test_differencing_would_flatten_a_stiff_transient` pins that case.

Rates do **not** follow the concentration groupings. `dA/dt` and `dEAact/dt`
both belong to stage 1, yet they differ by 60× at the defaults and by four
orders of magnitude when the enzymes are in excess:

| Band | Species | Peak \|rate\| (pM/s) |
|---|---|---|
| 10⁰ | `dA/dt`, `dE/dt`, `dEA/dt` | 4.04 |
| 10⁰ | `dC/dt` | 3.44 |
| 10⁰ | `dB/dt` | 1.80 |
| 10⁻¹ | `dF/dt`, `dFB/dt`, `dFBact/dt` | 0.45 / 0.37 / 0.12 |
| 10⁻² | `dEAact/dt` | 0.068 |

This is why the rate panels are grouped by magnitude across two rows rather than
by stage. At the defaults the total spread is only 60×, but the grouping has to
hold for whatever `E0` and `F0` the user sets — at `Cascade.m`'s values the same
nine rates span seven orders, and five distinct bands do not fit in three panels
without something being flattened onto the baseline.
