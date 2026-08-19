# PyInstaller build spec.  Build with:  uv run pyinstaller cascade.spec
#
# One-directory, not one-file.  A one-file build re-extracts the whole ~300 MB
# bundle to a temporary directory on every launch, which costs 10-30 seconds of
# startup; one-directory starts in a couple of seconds.  Ship the folder zipped.
# Switching is a matter of moving the binaries/datas into the EXE() call.

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

datas = [
    ("app.py", "."),                                  # the Streamlit script
    ("cascade/defaults.toml", "cascade"),             # parameter defaults
]
binaries = []

# The whole cascade package, whatever the import graph happens to reach.
# app.py is bundled as *data*, so PyInstaller never analyses it and never sees
# the modules it imports -- cascade.plots is imported only from there, and was
# silently left out of the build until this line was added.
hiddenimports = collect_submodules("cascade")

hiddenimports += [
    # st.dataframe and st.data_editor serialise through pyarrow.  Without it
    # the four parameter tables and the data table render empty -- the app
    # looks broken rather than failing loudly.
    "pyarrow",
    "pyarrow.vendored.version",
    # SciPy's solver backends are resolved by string name at call time, so
    # nothing static references them.
    "scipy.integrate",
    "scipy.special._special_ufuncs",
]

# Streamlit reads its own distribution metadata at import and raises without
# it.  The rest are collected so version lookups and entry points resolve.
for package in ("streamlit", "plotly", "pandas", "numpy", "scipy", "pyarrow"):
    datas += copy_metadata(package)

# Streamlit ships its compiled front end as package data; collect_all picks up
# the static assets along with the submodules.
for package in ("streamlit", "plotly"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden


a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Pulled in transitively but unused, and large.
        "matplotlib",
        "IPython",
        "notebook",
        "pytest",
        "tkinter",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="cascade",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,          # keep the console: it shows the local URL and errors
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="cascade",
)
