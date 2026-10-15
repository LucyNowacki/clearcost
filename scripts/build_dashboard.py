"""Build only the analytics artifacts, reusing the verified local cache by default."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from decision_lab.build import build, summary  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Fetch missing pinned CSVs; existing files are checksum-verified, never redownloaded")
    args = parser.parse_args()
    print(json.dumps(summary(build(ROOT, allow_download=args.download)), indent=2, allow_nan=False))
