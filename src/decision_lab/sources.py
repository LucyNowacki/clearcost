"""Immutable upstream sources and a checksum-verified local raw cache."""

import hashlib
import json
from pathlib import Path

import pandas as pd
import requests

CAB_COMMIT = "1fc686d1e8d01d23bd5be9316f77170ac0a7fcd8"
CAB_SOURCE_URL = f"https://github.com/DataGlacier/DataSets/tree/{CAB_COMMIT}"
NOTEBOOK_COMMIT = "76c2a3115b1c69d49eeddec109990b8ce3fcf842"
NOTEBOOK_URL = f"https://github.com/LucyNowacki/CAB_EDA/blob/{NOTEBOOK_COMMIT}/Cab_2.ipynb"
SOURCE_FILES = ("Cab_Data.csv", "Transaction_ID.csv", "Customer_ID.csv", "City.csv")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: dict) -> None:
    """Stable JSON, with no wall-clock timestamp or nonstandard NaN literals."""
    payload = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def fetch_sources(root: Path, *, allow_download: bool = False) -> dict:
    """Download missing sources only on request; never silently replace drift."""
    raw = root / "data" / "raw"
    manifest_path = root / "data" / "source_manifest.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {"source_url": CAB_SOURCE_URL, "commit": CAB_COMMIT, "files": {}}
    )
    if manifest.get("commit") != CAB_COMMIT or manifest.get("source_url") != CAB_SOURCE_URL:
        raise ValueError("Source manifest does not match the pinned CAB commit")
    for name in SOURCE_FILES:
        path = raw / name
        url = f"https://raw.githubusercontent.com/DataGlacier/DataSets/{CAB_COMMIT}/{name}"
        record = manifest["files"].get(name)
        if record and record.get("url") != url:
            raise ValueError(f"Unexpected source URL for {name}")
        if path.exists():
            if not record or sha256(path) != record["sha256"] or path.stat().st_size != record["bytes"]:
                raise ValueError(f"Unverified or modified raw cache: {name}")
            continue
        if not allow_download:
            raise FileNotFoundError(f"Missing {path}; run build_dashboard.py --download once")
        raw.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".csv.part")
        try:
            with requests.get(url, stream=True, timeout=(10, 120)) as response:
                response.raise_for_status()
                with temporary.open("wb") as stream:
                    for chunk in response.iter_content(1024 * 1024):
                        stream.write(chunk)
            digest = sha256(temporary)
            if record and digest != record["sha256"]:
                raise ValueError(f"Downloaded checksum mismatch: {name}")
            table = pd.read_csv(temporary)
            manifest["files"][name] = {
                "url": url,
                "sha256": digest,
                "bytes": temporary.stat().st_size,
                "rows": len(table),
                "columns": list(table.columns),
            }
            temporary.replace(path)
            write_json(manifest_path, manifest)
        finally:
            temporary.unlink(missing_ok=True)
    return manifest
