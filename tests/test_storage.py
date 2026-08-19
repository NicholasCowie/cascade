"""TOML round-tripping and the fingerprint behind the plot-reset rule."""

from __future__ import annotations

import tomllib

import pandas as pd
import pytest

from cascade.params import CATEGORIES, ParameterSet, load_defaults, units_flat
from cascade.simulate import SolverSettings, run_single, run_sweep
from cascade.storage import list_runs, load_run, run_path, safe_name, save_run


@pytest.fixture
def params():
    return load_defaults()[0]


@pytest.fixture
def metadata():
    return load_defaults()[1]


def test_kinetics_and_time_match_the_matlab_script(params):
    """The rate constants, time grid and sweep are Cascade.m's, unchanged."""
    import numpy as np

    assert params.k == pytest.approx(
        [
            np.log(2) / 120, 0.0, np.log(2) / 180, 0.0, 0.1,
            np.log(2) / 120, 0.0, np.log(2) / 180, 0.0, 0.1,
        ]
    )
    assert params.time["t_start"] == 0.0 and params.time["t_end"] == 600.0
    assert params.sweep_values() == [0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0]


def test_boundary_defaults_deliberately_differ_from_the_matlab_script(params):
    """Cascade.m starts both enzymes at 10000 pmol/L, far above the analyte.
    The project defaults put them at 35 and 40 pM instead -- comparable to the
    20 pM dose, so the enzymes are limiting and the cascade saturates.  Pinned
    here because that choice changes the regime, not just some numbers.
    """
    assert params.boundary == {"A0": 20.0, "E0": 35.0, "F0": 40.0}


def test_every_parameter_has_a_unit_and_description(metadata):
    for category in CATEGORIES:
        for name, entry in metadata[category].items():
            assert entry["unit"], f"{category}.{name} has no unit"
            assert entry["description"], f"{category}.{name} has no description"


def test_fingerprint_changes_for_any_edited_value(params):
    baseline = params.fingerprint()
    assert ParameterSet.from_dict(params.to_dict()).fingerprint() == baseline

    for category in CATEGORIES:
        for name in params.category(category):
            values = dict(params.category(category))
            values[name] = values[name] + 1.0
            edited = params.with_category(category, values)
            assert edited.fingerprint() != baseline, f"{category}.{name} not covered"


def test_round_trip_preserves_parameters_and_data(tmp_path, params, metadata):
    data = run_single(params)
    path = save_run(
        "baseline", params, data, units_flat(metadata),
        SolverSettings().to_dict(), results_dir=tmp_path,
    )

    restored = load_run(path)
    assert restored.params == params
    assert restored.params.fingerprint() == params.fingerprint()
    pd.testing.assert_frame_equal(restored.data, data)
    assert restored.units["k1f"] == "L/(pmol*s)"
    assert restored.solver["method"] == "LSODA"


def test_saved_file_carries_the_parameter_set(tmp_path, params, metadata):
    data = run_single(params)
    path = save_run(
        "baseline", params, data, units_flat(metadata),
        SolverSettings().to_dict(), results_dir=tmp_path,
    )

    with path.open("rb") as handle:
        document = tomllib.load(handle)

    for category in CATEGORIES:
        assert document[category] == params.category(category)
    assert document["schema"]["data"][0] == "time_s"
    assert "columns" not in document["data"], "[data] must hold only arrays"
    assert len(document["data"]["C"]) == len(data)
    assert document["name"] == "baseline"
    assert document["schema_version"] == 1


def test_sweep_round_trip_keeps_the_dose_response(tmp_path, params, metadata):
    timeseries, dose = run_sweep(params)
    path = save_run(
        "sweep", params, timeseries, units_flat(metadata),
        SolverSettings().to_dict(), dose_response=dose, results_dir=tmp_path,
    )

    restored = load_run(path)
    pd.testing.assert_frame_equal(restored.dose_response, dose)
    assert restored.data["A0_run"].nunique() == 9


def test_names_are_sanitised_into_filenames(tmp_path):
    assert safe_name("high dose / run #2") == "high-dose-run-2"
    assert safe_name("  ") == "run"
    assert safe_name("../../etc/passwd") == "etc-passwd"
    assert run_path("high dose", tmp_path).parent == tmp_path


def test_list_runs_reports_saved_runs(tmp_path, params, metadata):
    assert list_runs(tmp_path) == []

    save_run("first", params, run_single(params), units_flat(metadata),
             SolverSettings().to_dict(), results_dir=tmp_path)
    (tmp_path / "broken.toml").write_text("this is not = valid = toml")

    runs = list_runs(tmp_path)
    assert [item["name"] for item in runs] == ["first"]
    assert runs[0]["A0"] == 20.0 and runs[0]["swept"] is False


def test_data_section_loads_with_plain_pandas(tmp_path, params, metadata):
    """The file must be usable without importing this package at all:

        pd.DataFrame(tomllib.load(open(path, "rb"))["data"])

    That fails if anything other than the arrays lives in [data], which is why
    the column order is recorded under [schema].
    """
    timeseries, dose = run_sweep(params)
    path = save_run(
        "sweep", params, timeseries, units_flat(metadata),
        SolverSettings().to_dict(), dose_response=dose, results_dir=tmp_path,
    )

    with path.open("rb") as handle:
        document = tomllib.load(handle)

    rebuilt = pd.DataFrame(document["data"])
    pd.testing.assert_frame_equal(rebuilt, timeseries)
    pd.testing.assert_frame_equal(pd.DataFrame(document["dose_response"]), dose)


def test_schema_pins_column_order_even_if_the_file_is_reordered(tmp_path, params, metadata):
    data = run_single(params)
    path = save_run(
        "baseline", params, data, units_flat(metadata),
        SolverSettings().to_dict(), results_dir=tmp_path,
    )

    with path.open("rb") as handle:
        document = tomllib.load(handle)
    document["data"] = dict(reversed(list(document["data"].items())))

    import tomli_w

    path.write_bytes(tomli_w.dumps(document).encode())
    assert list(load_run(path).data.columns) == list(data.columns)
