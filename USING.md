# Using the cascade simulator

A guide for running the simulator from a downloaded build. No Python, no
installation and no terminal required.

## Starting it

Unzip the folder somewhere you can find again — the simulator saves your results
next to itself, so avoid opening it from inside the zip file.

| | |
|---|---|
| **Windows** | Open the folder and double-click **`cascade.exe`** |
| **macOS** | **Right-click** `cascade` and choose **Open**, then confirm |
| **Linux** | Double-click `cascade`, or run `./cascade` |

A small black console window appears — leave it open, it *is* the program — and
your web browser opens automatically. If it doesn't, the console prints an
address like `http://localhost:8501`; paste that into your browser.

**Closing the console window quits the simulator.** Closing the browser tab
alone does not.

> **macOS:** the first launch shows a warning because the build isn't signed by
> Apple. Right-click → Open gives you an "Open anyway" button; double-clicking
> does not. You only need to do this once.

> **Windows:** SmartScreen may show "Windows protected your PC" for the same
> reason. Click **More info** → **Run anyway**.

## What it simulates

A signal cascade in two stages. A small amount of analyte **A** triggers a much
larger amount of output **C** — the point of a cascade is amplification.

```
Stage 1:  A binds enzyme E  →  EA  →  activates to EAact  →  makes messenger B
Stage 2:  B binds enzyme F  →  FB  →  activates to FBact  →  makes output C
```

With the default settings, 20 pmol/L of A produces about 7000 pmol/L of C over
ten minutes — roughly 350-fold amplification.

## The parameter tables

Four tables, each listing a parameter, its **value**, its **unit** and a
description. Only the **Value** column can be edited: click a cell, type, press
Enter.

**Boundary conditions** — how much of each starting substance there is.
`A0` is the analyte dose (the interesting one); `E0` and `F0` are the two
enzymes.

**Kinetic parameters** — the ten rate constants, controlling how fast each step
runs. `k1f` and `k4f` are binding rates, `k2f` and `k5f` activation rates, `k3`
and `k6` production rates. The `b` versions (`k1b`, `k2b`, …) are the reverse
reactions, and are zero by default, meaning each step runs one way only.

**Time** — how long to simulate and how many points to record. `n_points` only
affects the resolution of the output, not the accuracy of the calculation.

**A0 sweep** — set `enabled` to `1` to run a series of analyte doses in one go
instead of a single dose, producing a dose-response curve. Set it back to `0`
for a single run.

## Running

Press **▶ Run simulation**. Results appear in a second or two.

**If you change any value, the plots disappear** and a message asks you to press
Run again. This is deliberate: it guarantees the picture on screen always matches
the numbers in the tables, so you can never misread an old plot as a new one.

## Reading the plots

The main figure is a grid. The **top two rows are concentrations** — how much of
each substance is present over time:

| | Complexes | Free enzyme | Stage output |
|---|---|---|---|
| **Stage 1** | A, EA, EAact | E | B |
| **Stage 2** | FB, FBact | F | C |

Each panel is separate because the amounts differ enormously — E sits near
10,000 pmol/L while A starts at 20. Drawn on shared axes, the small curves would
be flat lines on the bottom. The two stages are laid out to mirror each other,
and matching colours mean matching roles: E and F are both the free enzyme, EA
and FB both the complex.

The **bottom two rows are rates of change** — how *fast* each amount is moving,
rather than how much there is. These are grouped by size, because they range
from about 1000 down to 0.0001 pmol/L per second. A positive rate means the
substance is being made, negative means it is being consumed.

One curve is **dashed**: `dE/dt`, because it is mathematically identical to
`dA/dt` and would otherwise be hidden underneath it.

Some things worth knowing when the plots look surprising:

- **A vanishes almost instantly.** Binding is fast; A is essentially gone within
  the first second. That is the model behaving correctly.
- **B stays tiny** (~0.03 pmol/L). It is consumed as fast as it is produced,
  which is what makes the second stage run.
- **C only ever increases.** Nothing in the model removes it.

Every plot is interactive: hover for exact values, drag to zoom, double-click to
reset.

### Other controls

- **Y axis: linear / log** in the sidebar. Log makes small and large curves
  readable together. It applies to the concentration rows only — several rates
  are negative, and negative numbers cannot be drawn on a log scale.
- **Data table**, below the plots, gives the exact numbers behind every curve,
  with separate tabs for concentrations and rates.
- With the sweep on, a **dose selector** shows the full species detail for any
  single dose.

## Saving your results

Type a name in the sidebar and press **Save results**. This writes one file to
the `results` folder next to the program, for example `results/baseline.toml`.

Each file contains **both the data and every parameter that produced it**, so a
saved result can never be separated from its settings. You can open one in any
text editor to read the settings.

To return to earlier settings, pick the run under **Load** in the sidebar and
press **Load parameters** — the tables refill with those values, ready to run
again.

**Reset to defaults** restores the original settings at any time.

## If something goes wrong

**Nothing opens / blank page.** Check the console window for an address and open
it manually. If a previous copy is still running, the simulator picks a different
port automatically.

**Tables are empty.** Something is wrong with the build rather than your usage.
Open a terminal in the folder and run `cascade --selftest` (`.\cascade.exe
--selftest` on Windows); send whoever gave you the build the output.

**"Simulation failed".** Almost always an impossible setting — an end time
before the start time, fewer than two time points, or a sweep step of zero. The
message names the parameter. Press **Reset to defaults** to get back to a known
state.

**Results aren't saving.** The program writes next to itself, so it needs write
permission there. Move the folder out of `Program Files`, a read-only share, or
the zip file itself.
