"""Parameter sets: loading defaults, fingerprinting, TOML conversion."""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path

from .model import PARAM_ORDER

DEFAULTS_PATH = Path(__file__).with_name("defaults.toml")

# The three editable tables, plus the sweep controls.
CATEGORIES: tuple[str, ...] = ("boundary", "kinetics", "time", "sweep")

CATEGORY_LABELS: dict[str, str] = {
    "boundary": "Boundary conditions",
    "kinetics": "Kinetic parameters",
    "time": "Time",
    "sweep": "A0 sweep",
}

# Values are compared at this precision when deciding whether a parameter set
# has changed, so float noise from the UI does not spuriously reset the plot.
_FINGERPRINT_DECIMALS = 12


@dataclass(frozen=True)
class ParameterSet:
    """One complete set of inputs to a simulation."""

    boundary: dict[str, float]
    kinetics: dict[str, float]
    time: dict[str, float]
    sweep: dict[str, float]

    def category(self, name: str) -> dict[str, float]:
        return getattr(self, name)

    def with_category(self, name: str, values: dict[str, float]) -> "ParameterSet":
        """Return a copy with one category replaced."""
        return replace(self, **{name: dict(values)})

    # -- derived views --------------------------------------------------------

    @property
    def k(self) -> list[float]:
        """Rate constants in the order the model expects."""
        return [float(self.kinetics[name]) for name in PARAM_ORDER]

    @property
    def sweep_enabled(self) -> bool:
        return bool(round(float(self.sweep["enabled"])))

    def sweep_values(self) -> list[float]:
        """The A0 values to sweep, mirroring MATLAB's A0_start:step:A0_stop."""
        start = float(self.sweep["A0_start"])
        stop = float(self.sweep["A0_stop"])
        step = float(self.sweep["A0_step"])
        if step <= 0:
            raise ValueError("A0_step must be greater than zero.")
        if stop < start:
            raise ValueError("A0_stop must be greater than or equal to A0_start.")

        values: list[float] = []
        # Build by index rather than accumulating, to avoid drift; the small
        # tolerance keeps an inclusive endpoint when it lands on a step.
        n = int((stop - start) / step + 1e-9) + 1
        for i in range(n):
            values.append(start + i * step)
        return values

    # -- serialisation --------------------------------------------------------

    def to_dict(self) -> dict[str, dict[str, float]]:
        return {name: dict(self.category(name)) for name in CATEGORIES}

    @classmethod
    def from_dict(cls, data: dict) -> "ParameterSet":
        return cls(
            boundary={k: float(v) for k, v in data["boundary"].items()},
            kinetics={k: float(v) for k, v in data["kinetics"].items()},
            time={k: float(v) for k, v in data["time"].items()},
            sweep={k: float(v) for k, v in data["sweep"].items()},
        )

    def fingerprint(self) -> str:
        """Stable hash of every value, used to detect parameter changes.

        Covers all four categories, so editing any cell in any table -- or a
        sweep setting -- produces a different fingerprint and clears the plot.
        """
        canonical = {
            category: {
                key: round(float(value), _FINGERPRINT_DECIMALS)
                for key, value in sorted(self.category(category).items())
            }
            for category in CATEGORIES
        }
        blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()


def load_defaults(path: Path | None = None) -> tuple[ParameterSet, dict]:
    """Read defaults.toml into a ParameterSet plus its unit/description metadata."""
    doc = tomllib.loads((path or DEFAULTS_PATH).read_text())

    values: dict[str, dict[str, float]] = {}
    metadata: dict[str, dict[str, dict[str, str]]] = {}
    for category in CATEGORIES:
        entries = doc[category]
        values[category] = {k: float(v["value"]) for k, v in entries.items()}
        metadata[category] = {
            k: {"unit": v["unit"], "description": v["description"]}
            for k, v in entries.items()
        }

    return ParameterSet.from_dict(values), metadata


def units_flat(metadata: dict) -> dict[str, str]:
    """Flatten metadata to {parameter: unit} for storing alongside results."""
    return {
        key: entry["unit"]
        for category in metadata.values()
        for key, entry in category.items()
    }
