"""Compatibility entry point used by the parent project's README."""

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("build_dashboard.py")), run_name="__main__")
