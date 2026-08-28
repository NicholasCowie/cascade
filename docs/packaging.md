# Packaging

How the standalone build is produced, and why it is built the way it is.

The goal: hand someone a folder they can double-click, with no Python
installation, no terminal and no `pip`.

## Building

```sh
uv sync --all-groups
uv run pyinstaller cascade.spec --noconfirm
```

Output lands in `dist/cascade/` — an executable plus its `_internal/` support
directory, ~435 MB. Zip that folder to distribute it.

Verify the result **inside the bundle**, not from a source checkout:

```sh
cd dist/cascade
./cascade --selftest
```

```
  scipy      1.18.0
  pandas     3.0.5
  pyarrow    25.0.1
  modules    model, params, paths, plots, simulate, storage
  simulate   601 rows, C=1155.8
  rates      dC/dt=3.44
  plots      18 + 36 + 1 traces
  save/load  .../results/selftest.toml (ok)
  app        loaded, 4 tables rendered

Self-test passed.
```

Then `./cascade` to launch it for real.

## Cross-platform

**PyInstaller cannot cross-compile.** A Windows `.exe` must be built on Windows
and a macOS build on macOS. `.github/workflows/build.yml` runs the matrix on
`ubuntu-latest` and `windows-latest`, self-tests each bundle, and uploads it as
an artifact. macOS is left out on purpose, though no longer for cost — minutes
are free on a public repository. It is signing: see below. Adding it back is one
more entry in the matrix, plus that decision.

macOS builds are unsigned, so Gatekeeper blocks them on first launch. The
recipient needs to right-click → Open (not double-click) once, or the build must
be signed and notarised with an Apple Developer account.

### Getting a build without a machine to build it on

This is the only route to a Windows `.exe` from a Linux checkout, and it needs
no Windows machine at any point.

**Every push to `main`** produces both bundles. Open the repository's
**Actions** tab, pick the run, and download `cascade-windows` (or
`cascade-linux`) from the **Artifacts** section at the bottom of its summary
page. Artifacts last 7 days and can only be downloaded by someone signed in to
GitHub.

**Pushing a `v*` tag** additionally attaches the same zips to a GitHub
Release:

```sh
git tag v0.1.0
git push origin v0.1.0
```

The repository is public, so release assets download from the link alone, with
no GitHub account — which is what makes a build sendable to whoever asked for
it. Run artifacts are the opposite: they always require a signed-in account,
whatever the repository's visibility. That is the whole reason to cut a tag
rather than point somebody at the Actions tab.

Each bundle is zipped **on the runner that built it**, not by the upload step:
`actions/upload-artifact` dereferences symlinks and drops the executable bit,
which would leave the Linux and macOS binaries unable to start. The zip expands
to a `cascade/` folder, the same shape as a local `dist/cascade`. The runner
also deletes the `results/` directory the self-test writes, so the bundle
arrives without a saved run already in the picker.

The self-test step is the gate: a leg that builds but cannot import pyarrow, or
that is missing a module, fails there rather than shipping an artifact that
looks fine and renders empty tables.

## Design decisions

### One-directory, not one-file

`--onefile` re-extracts the entire ~300 MB bundle into a temporary directory on
**every** launch, giving a 10–30 second startup. One-directory starts in a couple
of seconds. Zip the folder for distribution instead. Switching is a matter of
moving `a.binaries` and `a.datas` into the `EXE()` call in `cascade.spec`.

### `bootstrap.run`, not the Streamlit CLI

The `streamlit` CLI re-executes itself as a subprocess. Under PyInstaller that
subprocess is the bundled executable again — which starts another server, which
spawns another. `launcher.py` calls `streamlit.web.bootstrap.run` directly,
skipping the CLI layer.

### Paths: two different roots

A frozen app has two locations and must not confuse them
(see [`cascade/paths.py`](../cascade/paths.py)):

| | Where | Used for |
|---|---|---|
| `bundle_root()` | `sys._MEIPASS` | read-only bundled data: `app.py`, `defaults.toml` |
| `results_dir()` | beside `sys.executable` | **written** files: saved runs |

Saved runs must land beside the executable. Writing them under `_MEIPASS` would
put them in a temporary directory that a one-file build deletes on exit — the
user's saved work would silently vanish. `tests/test_paths.py` simulates frozen
mode and asserts the two stay separate.

## Gotchas that cost real time

### Streamlit guesses "development mode" inside a bundle

The one that breaks everything. Streamlit decides development mode like this:

```python
return (not env_util.is_pex()
        and "site-packages" not in __file__
        and "dist-packages" not in __file__ ...)
```

Inside a bundle the path is `_internal/streamlit/config.py` — no `site-packages`
— so it concludes it is running from a **source checkout**. It then expects a
separate React dev server on port 3000, refuses to serve its own static assets
(every page 404s while `/_stcore/health` still returns `ok`, so the app looks
alive but blank), advertises `localhost:3000` to the browser, and forces DEBUG
logging.

Fix: set `global_developmentMode` to `False` explicitly.

### Config must go through `load_config_options`, with underscores

`bootstrap.run(..., flag_options=...)` does **not** apply the options — the CLI
normally applies them separately. Call `bootstrap.load_config_options()` first.

It converts keys with `name.replace("_", ".")`, so keys must be in underscore
form: `server_port`, not `server.port`. Dotted keys are silently ignored, with
no error — the app just runs on defaults.

### `browser_serverPort` must match `server_port`

They are separate settings. If only `server_port` is set, Streamlit opens the
browser at its own default port, where nothing is listening.

### pyarrow must be bundled explicitly

`st.dataframe` and `st.data_editor` serialise through pyarrow. Without it the
four parameter tables and the data table **render empty rather than raising** —
the app looks broken with no clue why. It is a `hiddenimport` in the spec, and
`--selftest` imports it deliberately for this reason.

### Package metadata

Streamlit reads its own distribution metadata at import and fails without it.
The spec calls `copy_metadata` for `streamlit`, `plotly`, `pandas`, `numpy`,
`scipy` and `pyarrow`, and `collect_all` for `streamlit` and `plotly` to pick up
the compiled front-end assets.

## Routes considered and rejected

**`streamlit-desktop-app`** — the obvious turnkey wrapper (pywebview +
PyInstaller). Requires Python < 3.13; this project is pinned to 3.13. Last
released December 2024.

**stlite / Pyodide (WebAssembly)** — runs Streamlit in the browser with no
Python interpreter at all; scipy, numpy and pandas are built into Pyodide. Two
blockers for this app:

- The filesystem is an ephemeral virtual one. Saving `results/*.toml` would have
  to become download buttons or a NODEFS mount, changing a feature that
  currently works.
- A loose stlite `index.html` **cannot be opened over `file://`** — it must be
  served over HTTP. So it cannot simply be emailed to someone. The Electron
  wrapper (`@stlite/desktop`) solves that by serving the bundle internally, at
  the cost of a Node/Electron toolchain and the filesystem rework.

Worth revisiting if the download-instead-of-save trade becomes acceptable: the
result needs no Python on the target machine at all.

**Docker** — requires Docker on the recipient's machine, which is a bigger ask
than a Python environment for the intended audience.
