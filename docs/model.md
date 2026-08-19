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

| Quantity | Nine integrated states | Seven states + balances |
|---|---|---|
| `F + FB + FBact` residual | 5.5 × 10⁻¹¹ | 1.8 × 10⁻¹² |
| `E + EA + EAact` residual | — | exactly 0.0 |

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

Carried over verbatim from `Cascade.m`, and editable in
[`cascade/defaults.toml`](../cascade/defaults.toml):

| Parameter | Value | Unit | Meaning |
|---|---|---|---|
| `A0` | 20 | pmol/L | initial analyte |
| `E0`, `F0` | 10000 | pmol/L | initial enzymes |
| `k1f`, `k4f` | ln2/120 ≈ 5.776×10⁻³ | L/(pmol·s) | association |
| `k2f`, `k5f` | ln2/180 ≈ 3.851×10⁻³ | 1/s | activation |
| `k3`, `k6` | 0.1 | 1/s | production |
| `k1b`, `k2b`, `k4b`, `k5b` | 0 | 1/s | reverse steps |
| time | 0 … 600, 601 points | s | |
| sweep | A0 = 0 : 5 : 40 | pmol/L | |

**Units correction.** `Cascade.m:4` labels all ten rate constants `1/s`. But
`k1f` and `k4f` multiply a *product of two concentrations*, so dimensional
consistency requires `L/(pmol·s)`; the other eight are `1/s`. The app displays
the corrected units. **The numbers are unchanged.**

## Integration

`ode15s` becomes `scipy.integrate.solve_ivp(method="LSODA")`, which likewise
switches between stiff and non-stiff methods internally. The system is genuinely
stiff: with the default rates, `k1f·A·E ≈ 1155 pmol/L/s` at t = 0, so A is
consumed within milliseconds, while C accrues over minutes.

Defaults are `rtol=1e-8`, `atol=1e-10`; the app exposes the method and tolerance
in the sidebar. `test_lsoda_agrees_with_a_stiff_reference` pins LSODA against
tight-tolerance `Radau`.

## Rates of change

`simulate.rates` evaluates `rhs` at each stored timepoint rather than
differencing the solution. This matters at t = 0: the true `dA/dt` is
−1155 pmol/L/s, but differencing over the 1 s output step reports only −20,
because A is gone long before the next sample. Differencing understates the
transient by a factor of 58.

Rates span seven orders of magnitude, and the bands do **not** follow the
concentration groupings — `dA/dt` and `dEAact/dt` both belong to stage 1 yet
differ by 15,000×:

| Band | Species | Peak \|rate\| (pmol/L/s) |
|---|---|---|
| 10³ | `dA/dt`, `dE/dt`, `dEA/dt` | 1155 (a t = 0 transient) |
| 10¹ | `dC/dt` | 38.3 |
| 10⁰ | `dF/dt`, `dFBact/dt`, `dFB/dt` | 1.8 / 1.34 / 0.74 |
| 10⁻² | `dEAact/dt` | 0.077 |
| 10⁻⁴ | `dB/dt` | 0.000133 |

This is why the rate panels are grouped by magnitude and need two rows: five
bands do not fit in three panels without something being flattened onto the
baseline.
