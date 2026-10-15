"""Fetch the pinned CAB sources once into the ignored raw cache."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from decision_lab.sources import fetch_sources  # noqa: E402

if __name__ == "__main__":
    print(json.dumps(fetch_sources(ROOT, allow_download=True), indent=2))
