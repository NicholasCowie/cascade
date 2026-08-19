"""Locating files, both in the source tree and inside a PyInstaller bundle.

PyInstaller moves everything.  Bundled read-only data is unpacked into a
temporary directory that ``sys._MEIPASS`` points at, while ``sys.executable``
is the binary the user actually double-clicked.  The two must not be confused:
anything the app *writes* has to go beside the executable, because the
unpacked directory is disposable -- with a one-file build it is deleted when
the app exits, taking any saved run with it.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The repository root when running from source: cascade/paths.py -> cascade -> .
_SOURCE_ROOT = Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    """True when running from a PyInstaller build rather than the source tree."""
    return getattr(sys, "frozen", False)


def bundle_root() -> Path:
    """Where read-only bundled files live -- ``app.py``, ``defaults.toml``.

    PyInstaller sets ``sys._MEIPASS`` for both one-file and one-directory
    builds; falling back to the source root keeps the same call working during
    development.
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return _SOURCE_ROOT


def results_dir() -> Path:
    """Where saved runs are written.

    Beside the executable when frozen, so the user can find their files next
    to the thing they launched, and so a one-file build does not discard them
    with its temporary directory.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent / "results"
    return _SOURCE_ROOT / "results"


def app_script() -> Path:
    """The Streamlit script the launcher runs."""
    return bundle_root() / "app.py"
