"""Launcher: `uv run main.py` opens the cascade app in a browser."""

from __future__ import annotations

import sys
from pathlib import Path

from streamlit.web import cli


def main() -> int:
    app = Path(__file__).resolve().parent / "app.py"
    sys.argv = ["streamlit", "run", str(app), *sys.argv[1:]]
    return cli.main()


if __name__ == "__main__":
    raise SystemExit(main())
