"""End-to-end checks on the Streamlit app, driven headlessly by AppTest.

AppTest renders `st.data_editor` as a dataframe element and does not expose
Plotly charts, so edits are injected through the editors' widget state and the
assertions are made against session state and the app's own messages.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

TIMEOUT = 60
APP = Path(__file__).resolve().parent.parent / "app.py"
EDITOR_COUNT = 4  # boundary, time, sweep, kinetics


def _app() -> AppTest:
    app = AppTest.from_file(str(APP), default_timeout=TIMEOUT)
    app.run()
    assert not app.exception
    return app


def _run_button(app: AppTest):
    return next(button for button in app.button if "Run simulation" in button.label)


def _editor_key(app: AppTest, category: str) -> str:
    return next(
        key
        for key in app.session_state.filtered_state
        if key.startswith(f"editor_{category}_")
    )


def _edit(app: AppTest, category: str, parameter: str, value: float) -> AppTest:
    """Change one cell of one parameter table, as a user would."""
    row = list(app.session_state.params.category(category)).index(parameter)
    app.session_state[_editor_key(app, category)] = {
        "edited_rows": {row: {"Value": value}},
        "added_rows": [],
        "deleted_rows": [],
    }
    return app


def _prompted_to_run(app: AppTest) -> bool:
    return any("Run simulation" in info.value for info in app.info)


def test_app_starts_with_no_plot_and_the_matlab_defaults():
    app = _app()
    assert app.session_state.results is None
    assert app.session_state.params.boundary["A0"] == 20.0
    assert app.session_state.params.time["t_end"] == 600.0
    assert len([k for k in app.session_state.filtered_state if "editor_" in k]) == (
        EDITOR_COUNT
    )
    assert _prompted_to_run(app)


def test_units_are_displayed_for_every_parameter():
    app = _app()
    units = {}
    for element in app.get("dataframe"):
        frame = element.value
        units.update(dict(zip(frame["Parameter"], frame["Unit"])))
    assert units["A0"] == "pmol/L"
    assert units["k1f"] == "L/(pmol*s)"
    assert units["t_start"] == "s"


def test_run_produces_results():
    app = _app()
    _run_button(app).click().run()

    assert not app.exception
    results = app.session_state.results
    assert results is not None
    assert list(results["data"].columns)[0] == "time_s"
    assert len(results["data"]) == 601
    assert results["data"]["C"].iloc[-1] > 0
    assert results["dose"] is None
    assert not _prompted_to_run(app)


def test_editing_a_parameter_resets_the_plot():
    app = _app()
    _run_button(app).click().run()
    assert app.session_state.results is not None

    _edit(app, "boundary", "A0", 25.0).run()

    assert app.session_state.params.boundary["A0"] == 25.0
    assert app.session_state.results is None, "stale plot survived a parameter change"
    assert _prompted_to_run(app)


@pytest.mark.parametrize(
    ("category", "parameter", "value"),
    [
        ("boundary", "E0", 5000.0),
        ("kinetics", "k3", 0.2),
        ("time", "t_end", 300.0),
        ("sweep", "A0_step", 10.0),
    ],
)
def test_every_category_resets_the_plot(category, parameter, value):
    app = _app()
    _run_button(app).click().run()
    assert app.session_state.results is not None

    _edit(app, category, parameter, value).run()
    assert app.session_state.results is None


def test_rerunning_after_an_edit_restores_the_plot():
    app = _app()
    _run_button(app).click().run()
    _edit(app, "time", "t_end", 300.0).run()
    assert app.session_state.results is None

    _run_button(app).click().run()
    assert app.session_state.results is not None
    assert app.session_state.results["data"]["time_s"].iloc[-1] == 300.0


def test_enabling_the_sweep_produces_a_dose_response():
    app = _app()
    _edit(app, "sweep", "enabled", 1.0).run()
    _run_button(app).click().run()

    assert not app.exception
    results = app.session_state.results
    assert results["dose"] is not None
    assert len(results["dose"]) == 9
    assert results["dose"]["C_final"].is_monotonic_increasing
    assert results["data"]["A0_run"].nunique() == 9


def test_saving_writes_a_toml_that_loads_back(tmp_path, monkeypatch):
    monkeypatch.setattr("cascade.storage.RESULTS_DIR", tmp_path)

    app = _app()
    _run_button(app).click().run()
    next(button for button in app.button if button.label == "Save results").click().run()

    assert not app.exception
    written = list(tmp_path.glob("*.toml"))
    assert [path.name for path in written] == ["baseline.toml"]
    assert any("Saved" in success.value for success in app.success)

    from cascade.storage import load_run

    restored = load_run(written[0])
    assert restored.params == app.session_state.params
    assert len(restored.data) == 601


def test_loading_a_saved_run_repopulates_the_tables(tmp_path, monkeypatch):
    monkeypatch.setattr("cascade.storage.RESULTS_DIR", tmp_path)

    app = _app()
    _edit(app, "boundary", "A0", 33.0).run()
    _run_button(app).click().run()
    next(button for button in app.button if button.label == "Save results").click().run()

    app = _app()  # a fresh session, back at the defaults
    assert app.session_state.params.boundary["A0"] == 20.0

    next(b for b in app.button if b.label == "Load parameters").click().run()
    assert not app.exception
    assert app.session_state.params.boundary["A0"] == 33.0
    assert app.session_state.results is None


def test_reset_restores_the_defaults():
    app = _app()
    _edit(app, "kinetics", "k6", 0.9).run()
    assert app.session_state.params.kinetics["k6"] == 0.9

    next(b for b in app.button if b.label == "Reset to defaults").click().run()
    assert app.session_state.params.kinetics["k6"] == 0.1


def test_an_invalid_time_grid_reports_an_error_instead_of_plotting():
    app = _app()
    _edit(app, "time", "n_points", 1.0).run()
    _run_button(app).click().run()

    assert not app.exception
    assert app.session_state.results is None
    assert any("n_points" in error.value for error in app.error)
