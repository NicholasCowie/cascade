"""Entry point for the packaged build.

Starts the Streamlit server in-process and lets it open a browser.

This calls ``streamlit.web.bootstrap.run`` rather than the ``streamlit`` CLI.
The CLI re-executes itself as a subprocess, and under PyInstaller that
subprocess is the bundled executable again -- which starts another server,
which spawns another, until the machine gives up.  ``bootstrap.run`` skips the
CLI layer entirely and just runs the script.

Run with ``--selftest`` to check the bundle end to end without a browser.
"""

from __future__ import annotations

import socket
import sys

from streamlit.web import bootstrap

from cascade import paths

DEFAULT_PORT = 8501


def free_port(preferred: int = DEFAULT_PORT) -> int:
    """The preferred port if it is free, otherwise one the OS picks.

    A second copy of the app, or anything else already on 8501, should not stop
    this one starting.
    """
    with socket.socket() as probe:
        try:
            probe.bind(("localhost", preferred))
        except OSError:
            pass
        else:
            return preferred

    with socket.socket() as probe:
        probe.bind(("localhost", 0))
        return int(probe.getsockname()[1])


def selftest() -> int:
    """Exercise the whole pipeline inside the bundle and report.

    Worth having in the shipped build: it is the only way to tell a packaging
    problem (a missing scipy backend, pyarrow left out so tables render empty)
    from a broken machine, and it needs no browser.
    """
    from cascade.params import load_defaults, units_flat
    from cascade.simulate import SolverSettings, rates, run_single
    from cascade.storage import load_run, save_run

    checks: list[tuple[str, str]] = []

    import pandas
    import pyarrow
    import scipy

    checks.append(("scipy", scipy.__version__))
    checks.append(("pandas", pandas.__version__))
    # Not imported by this module, but st.dataframe serialises through it; if
    # it were missing from the bundle every table would render empty.
    checks.append(("pyarrow", pyarrow.__version__))

    params, metadata = load_defaults()
    frame = run_single(params)
    rate_frame = rates(frame, params)
    checks.append(("simulate", f"{len(frame)} rows, C={frame['C'].iloc[-1]:.1f}"))
    checks.append(("rates", f"dC/dt={rate_frame['dC_dt'].iloc[-1]:.2f}"))

    path = save_run(
        "selftest", params, frame, units_flat(metadata), SolverSettings().to_dict()
    )
    restored = load_run(path)
    ok = restored.params == params and len(restored.data) == len(frame)
    checks.append(("save/load", f"{path} ({'ok' if ok else 'MISMATCH'})"))

    width = max(len(name) for name, _ in checks)
    for name, detail in checks:
        print(f"  {name:<{width}}  {detail}")

    if not ok:
        print("\nSelf-test FAILED: saved run did not round-trip.", file=sys.stderr)
        return 1
    print(f"\nSelf-test passed. Results directory: {paths.results_dir()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if "--selftest" in argv:
        return selftest()

    script = paths.app_script()
    if not script.is_file():
        print(f"Cannot find the app script at {script}", file=sys.stderr)
        return 1

    port = free_port()
    print(
        "Cascade simulator\n"
        f"  opening   http://localhost:{port}\n"
        f"  saving to {paths.results_dir()}\n"
        "  close this window to quit",
        flush=True,
    )

    # Keys use the CLI's underscore form: load_config_options turns each "_"
    # into a "." Passing dotted keys here silently does nothing.
    flag_options = {
        "server_port": port,
        # What Streamlit prints and opens in the browser.  If this disagrees
        # with server_port the browser lands on a port nothing listens on.
        "browser_serverPort": port,
        # Not headless, so Streamlit opens the browser itself.
        "server_headless": False,
        "browser_gatherUsageStats": False,
        # The one that matters most in a build.  Streamlit decides development
        # mode by looking for "site-packages" in its own __file__; inside a
        # PyInstaller bundle the path is _internal/streamlit/, so it guesses
        # *development* and then expects a separate React dev server on port
        # 3000 -- refusing to serve its own static assets, so every page is a
        # 404, and forcing debug logging.
        "global_developmentMode": False,
        # Nothing to reload in a build; the watcher is only startup cost.
        "server_fileWatcherType": "none",
    }

    # Applies config.toml plus these overrides.  bootstrap.run does not do
    # this itself -- the CLI normally does it before calling run.
    bootstrap.load_config_options(flag_options)

    bootstrap.run(str(script), is_hello=False, args=[], flag_options=flag_options)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
