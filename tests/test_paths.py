"""Path resolution in the source tree and in a PyInstaller build.

The build cannot be exercised from a test, so frozen mode is simulated by
setting the two attributes PyInstaller sets.  What matters is the split: read-
only data comes out of the bundle, but anything written goes beside the
executable -- a one-file build deletes its unpack directory on exit, so a run
saved there would be lost.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cascade import paths

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def frozen(monkeypatch, tmp_path):
    """Simulate a PyInstaller build: bundle unpacked in one place, executable
    in another."""
    bundle = tmp_path / "unpacked"
    installed = tmp_path / "installed"
    bundle.mkdir()
    installed.mkdir()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(sys, "executable", str(installed / "cascade"), raising=False)
    return bundle, installed


def test_source_layout_when_not_frozen():
    assert not paths.is_frozen()
    assert paths.bundle_root() == REPO_ROOT
    assert paths.results_dir() == REPO_ROOT / "results"
    assert paths.app_script() == REPO_ROOT / "app.py"


def test_app_script_exists_where_it_is_claimed():
    assert paths.app_script().is_file()


def test_frozen_reads_from_the_bundle(frozen):
    bundle, _ = frozen
    assert paths.is_frozen()
    assert paths.bundle_root() == bundle
    assert paths.app_script() == bundle / "app.py"


def test_frozen_writes_beside_the_executable(frozen):
    """The regression this exists to prevent: saving into the bundle's
    temporary directory, where a one-file build discards it on exit."""
    bundle, installed = frozen
    assert paths.results_dir() == installed / "results"
    assert bundle not in paths.results_dir().parents
    assert paths.results_dir() != paths.bundle_root() / "results"


def test_frozen_falls_back_when_meipass_is_absent(monkeypatch, tmp_path):
    """One-directory builds set _MEIPASS too, but do not depend on it."""
    installed = tmp_path / "installed"
    installed.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(sys, "executable", str(installed / "cascade"), raising=False)

    assert paths.bundle_root() == installed
    assert paths.results_dir() == installed / "results"


def test_storage_anchors_its_results_dir_to_paths():
    from cascade import storage

    assert storage.RESULTS_DIR == paths.results_dir()
