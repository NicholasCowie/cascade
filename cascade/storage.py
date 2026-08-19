"""Saving and loading runs as TOML.

One file per run holds the parameter set *and* the simulated data, so a result
is always self-describing.  Reading uses the standard library's ``tomllib``;
writing needs ``tomli_w`` (the stdlib has no TOML writer).

pandas cannot read TOML directly, so ``load_run`` rebuilds the DataFrame from
the column arrays in ``[data]``.  Results are pandas objects everywhere in the
app -- only the on-disk format differs.

``[data]`` holds nothing but the arrays, so the obvious one-liner works without
this module::

    import tomllib, pandas as pd
    pd.DataFrame(tomllib.load(open("results/baseline.toml", "rb"))["data"])

Column order is recorded separately under ``[schema]`` rather than inside
``[data]``, where it would have collided with the arrays.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
import tomli_w

from . import paths
from .params import CATEGORIES, ParameterSet

# Resolved once at import: whether the app is frozen cannot change at runtime.
# In a PyInstaller build this points beside the executable rather than into the
# bundle's temporary unpack directory -- see cascade/paths.py.
RESULTS_DIR = paths.results_dir()
SCHEMA_VERSION = 1

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class SavedRun:
    """A run read back off disk."""

    name: str
    path: Path
    params: ParameterSet
    data: pd.DataFrame
    dose_response: pd.DataFrame | None
    units: dict[str, str]
    solver: dict
    saved_at: str


def safe_name(name: str) -> str:
    """Turn a user-supplied run name into a filename stem."""
    cleaned = _UNSAFE.sub("-", name.strip()).strip("-.")
    return cleaned or "run"


def run_path(name: str, results_dir: Path | None = None) -> Path:
    return (results_dir or RESULTS_DIR) / f"{safe_name(name)}.toml"


def _columns(frame: pd.DataFrame) -> dict:
    """Column-oriented arrays, and nothing else -- see the module docstring."""
    return {column: [float(v) for v in frame[column]] for column in frame.columns}


def save_run(
    name: str,
    params: ParameterSet,
    data: pd.DataFrame,
    units: dict[str, str],
    solver: dict,
    dose_response: pd.DataFrame | None = None,
    saved_at: datetime | None = None,
    results_dir: Path | None = None,
) -> Path:
    """Write results/<name>.toml.  Returns the path written."""
    directory = results_dir or RESULTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = run_path(name, directory)

    document: dict = {
        "name": name,
        "saved_at": (saved_at or datetime.now()).isoformat(timespec="seconds"),
        "schema_version": SCHEMA_VERSION,
        "solver": dict(solver),
    }
    for category in CATEGORIES:
        document[category] = dict(params.category(category))
    document["units"] = dict(units)
    document["schema"] = {"data": list(data.columns)}
    document["data"] = _columns(data)
    if dose_response is not None:
        document["schema"]["dose_response"] = list(dose_response.columns)
        document["dose_response"] = _columns(dose_response)

    path.write_bytes(tomli_w.dumps(document).encode())
    return path


def _frame(section: dict, order: list[str] | None = None) -> pd.DataFrame:
    """Rebuild a DataFrame; TOML preserves insertion order, and [schema] pins
    it explicitly for files that have been hand-edited or reordered."""
    columns = order or list(section)
    return pd.DataFrame({column: section[column] for column in columns})


def load_run(path: Path) -> SavedRun:
    """Read a run back, rebuilding the DataFrames from the TOML arrays."""
    with Path(path).open("rb") as handle:
        document = tomllib.load(handle)

    schema = document.get("schema", {})
    dose = document.get("dose_response")
    return SavedRun(
        name=document.get("name", Path(path).stem),
        path=Path(path),
        params=ParameterSet.from_dict(document),
        data=_frame(document["data"], schema.get("data")),
        dose_response=_frame(dose, schema.get("dose_response")) if dose else None,
        units=document.get("units", {}),
        solver=document.get("solver", {}),
        saved_at=document.get("saved_at", ""),
    )


def list_runs(results_dir: Path | None = None) -> list[dict]:
    """Summarise saved runs for the sidebar picker, newest first."""
    directory = results_dir or RESULTS_DIR
    if not directory.exists():
        return []

    summaries: list[dict] = []
    for path in sorted(directory.glob("*.toml")):
        try:
            with path.open("rb") as handle:
                document = tomllib.load(handle)
        except (tomllib.TOMLDecodeError, OSError):
            continue  # a hand-edited or partial file should not break the picker
        summaries.append(
            {
                "name": document.get("name", path.stem),
                "path": path,
                "saved_at": document.get("saved_at", ""),
                "A0": document.get("boundary", {}).get("A0"),
                "swept": "dose_response" in document,
            }
        )

    summaries.sort(key=lambda item: item["saved_at"], reverse=True)
    return summaries
