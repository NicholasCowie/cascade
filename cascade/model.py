"""The cascade ODE system, translated from Cascade.m.

A two-stage enzymatic signal cascade.  Analyte A binds enzyme E to form the
complex EA, which activates to EAact.  EAact produces the messenger B, which
drives an identical bind -> activate -> produce stage on F, yielding the
output C.

Cascade.m integrates all nine species.  Two of them are redundant: adding the
E, EA and EAact rows of that system cancels every term, so E + EA + EAact can
never leave E0, and likewise F + FB + FBact can never leave F0.  ``rhs`` below
therefore integrates seven states and recovers E and F from those balances,
which holds them at exactly E0 and F0 instead of letting the integrator drift.

``rhs_full`` keeps the original nine-equation transcription.  Nothing in the
app uses it; it exists so the tests can check the reduction against the system
it came from.
"""

from __future__ import annotations

import numpy as np

# The nine species, in the order Cascade.m lists them.  This is the shape of
# the *output*: every species is reported, whether integrated or recovered.
SPECIES: tuple[str, ...] = (
    "A",
    "E",
    "EA",
    "EAact",
    "B",
    "F",
    "FB",
    "FBact",
    "C",
)

# The seven states actually integrated -- E and F are left out.
STATE: tuple[str, ...] = ("A", "EA", "EAact", "B", "FB", "FBact", "C")

# Recovered from a conservation balance rather than integrated.
DERIVED: tuple[str, ...] = ("E", "F")

# Order matches k = [k1f k1b k2f k2b k3 k4f k4b k5f k5b k6] in Cascade.m.
PARAM_ORDER: tuple[str, ...] = (
    "k1f",
    "k1b",
    "k2f",
    "k2b",
    "k3",
    "k4f",
    "k4b",
    "k5f",
    "k5b",
    "k6",
)


def free_enzymes(x, E0: float, F0: float) -> tuple[float, float]:
    """E and F from the balances E + EA + EAact = E0, F + FB + FBact = F0."""
    _, EA, EAact, _, FB, FBact, _ = x
    return E0 - EA - EAact, F0 - FB - FBact


def rhs(t: float, x, k, E0: float, F0: float) -> np.ndarray:
    """Right-hand side of the reduced system, in ``STATE`` order.

    ``t`` is unused (the system is autonomous) but kept in the signature for
    ``scipy.integrate.solve_ivp``.
    """
    A, EA, EAact, B, FB, FBact, C = x
    k1f, k1b, k2f, k2b, k3, k4f, k4b, k5f, k5b, k6 = k
    E, F = free_enzymes(x, E0, F0)

    return np.array(
        [
            -k1f * A * E + k1b * EA,
            k1f * A * E - k1b * EA - k2f * EA + k2b * EAact,
            k2f * EA - k2b * EAact,
            k3 * EAact - k4f * B * F + k4b * FB,
            k4f * B * F - k4b * FB - k5f * FB + k5b * FBact,
            k5f * FB - k5b * FBact,
            k6 * FBact,
        ]
    )


def rhs_full(t: float, x, k) -> np.ndarray:
    """The original nine-equation system from Cascade.m:17-25.

    Reference only -- the app integrates ``rhs``.  Kept so the reduction can be
    checked against the equations it was derived from.
    """
    A, E, EA, EAact, B, F, FB, FBact, C = x
    k1f, k1b, k2f, k2b, k3, k4f, k4b, k5f, k5b, k6 = k

    return np.array(
        [
            -k1f * A * E + k1b * EA,
            -k1f * A * E + k1b * EA,
            k1f * A * E - k1b * EA - k2f * EA + k2b * EAact,
            k2f * EA - k2b * EAact,
            k3 * EAact - k4f * B * F + k4b * FB,
            -k4f * B * F + k4b * FB,
            k4f * B * F - k4b * FB - k5f * FB + k5b * FBact,
            k5f * FB - k5b * FBact,
            k6 * FBact,
        ]
    )


def initial_state(A0: float) -> np.ndarray:
    """x0 for the reduced system: only A starts non-zero."""
    return np.array([A0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=float)


def initial_state_full(A0: float, E0: float, F0: float) -> np.ndarray:
    """x0 = [A0; E0; 0; 0; 0; F0; 0; 0; 0], as in Cascade.m:9."""
    return np.array([A0, E0, 0.0, 0.0, 0.0, F0, 0.0, 0.0, 0.0], dtype=float)


def expand(states: np.ndarray, E0: float, F0: float) -> np.ndarray:
    """Turn integrated states (n, 7) into every species (n, 9).

    E and F come from the balances rather than the integrator, so they are
    exact by construction.
    """
    states = np.atleast_2d(states)
    A, EA, EAact, B, FB, FBact, C = states.T
    E = E0 - EA - EAact
    F = F0 - FB - FBact
    return np.column_stack([A, E, EA, EAact, B, F, FB, FBact, C])


def expand_rates(derivatives: np.ndarray) -> np.ndarray:
    """Turn state derivatives (n, 7) into rates for every species (n, 9).

    dE/dt = -(dEA/dt + dEAact/dt) and dF/dt = -(dFB/dt + dFBact/dt) follow by
    differentiating the balances, so these are exact too.
    """
    derivatives = np.atleast_2d(derivatives)
    dA, dEA, dEAact, dB, dFB, dFBact, dC = derivatives.T
    dE = -(dEA + dEAact)
    dF = -(dFB + dFBact)
    return np.column_stack([dA, dE, dEA, dEAact, dB, dF, dFB, dFBact, dC])
