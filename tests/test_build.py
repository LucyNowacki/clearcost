from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from decision_lab.build import build
from decision_lab.sources import CAB_COMMIT, CAB_SOURCE_URL, SOURCE_FILES, fetch_sources, sha256, write_json
from decision_lab.validation import validate_dashboard

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def dashboard():
    path = ROOT / "dist" / "data" / "dashboard.json"
    if not path.exists():
        pytest.skip("Build dashboard first for artifact integration tests")
    return json.loads(path.read_text())


def test_dashboard_contract(dashboard):
    validate_dashboard(dashboard)
    assert dashboard["meta"]["row_count"] == 359392
    assert dashboard["meta"]["cab_commit"] == CAB_COMMIT
    assert dashboard["meta"]["date_start"] == "2016-01-02"
    assert dashboard["meta"]["date_end"] == "2018-12-31"
    assert len(dashboard["cab"]["monthly"]) == 36 * 2 * 19


@pytest.mark.parametrize("defect", ["raw_id", "synthetic", "currency", "split", "budget", "metric", "nonfinite", "multiplier", "missing_multiplier", "response"])
def test_publication_boundary_rejects_defects(dashboard, defect):
    bad = deepcopy(dashboard)
    if defect == "raw_id":
        bad["cab"]["monthly"][0]["customer_id"] = 123
    elif defect == "synthetic":
        bad["media"]["synthetic"] = False
    elif defect == "currency":
        bad["media"]["currency"] = "USD"
    elif defect == "split":
        bad["media"]["weekly"][130]["split"] = "train"
    elif defect == "budget":
        bad["media"]["plans"][0]["shares"]["search"] = 0.9
    elif defect == "metric":
        bad["cab"]["forecast"][0]["mae"] = 0
    elif defect == "multiplier":
        bad["media"]["channels"][0]["steady_state_multiplier"] = 1
    elif defect == "missing_multiplier":
        del bad["media"]["channels"][0]["steady_state_multiplier"]
    elif defect == "response":
        bad["media"]["plans"][0]["incremental_revenue"] += 100
    else:
        bad["media"]["weekly"][0]["revenue"] = float("nan")
    with pytest.raises(ValueError):
        validate_dashboard(bad)


def test_cache_is_checked_and_not_downloaded_again(tmp_path, monkeypatch):
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    manifest = {"commit": CAB_COMMIT, "source_url": CAB_SOURCE_URL, "files": {}}
    for name in SOURCE_FILES:
        path = raw / name
        path.write_bytes(b"a,b\n1,2\n")
        manifest["files"][name] = {"url": f"https://raw.githubusercontent.com/DataGlacier/DataSets/{CAB_COMMIT}/{name}", "sha256": sha256(path), "bytes": path.stat().st_size}
    write_json(tmp_path / "data" / "source_manifest.json", manifest)

    def no_network(*args, **kwargs):
        pytest.fail("Cache reuse must not access the network")

    monkeypatch.setattr("decision_lab.sources.requests.get", no_network)
    assert fetch_sources(tmp_path, allow_download=True) == manifest
    (raw / SOURCE_FILES[0]).write_bytes(b"modified")
    with pytest.raises(ValueError, match="modified raw cache"):
        fetch_sources(tmp_path, allow_download=True)


def test_missing_cache_is_offline_by_default(tmp_path):
    with pytest.raises(FileNotFoundError, match="--download"):
        fetch_sources(tmp_path)


def test_manifest_matches_built_artifact(dashboard):
    manifest = json.loads((ROOT / "dist" / "data" / "manifest.json").read_text())
    assert manifest["artifact"]["sha256"] == sha256(ROOT / "dist" / "data" / "dashboard.json")
    assert manifest["artifact"]["raw_customer_rows_exported"] is False
    assert (ROOT / "data" / "manifest.json").read_bytes() == (ROOT / "dist" / "data" / "manifest.json").read_bytes()


def test_two_offline_builds_are_byte_identical(tmp_path, monkeypatch):
    if not (ROOT / "data" / "raw" / SOURCE_FILES[0]).exists():
        pytest.skip("Pinned raw cache required for full offline build integration test")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "raw").symlink_to(ROOT / "data" / "raw", target_is_directory=True)
    shutil.copy2(ROOT / "data" / "source_manifest.json", tmp_path / "data" / "source_manifest.json")

    def no_network(*args, **kwargs):
        pytest.fail("Build must be offline after the initial download")

    monkeypatch.setattr("decision_lab.sources.requests.get", no_network)
    build(tmp_path)
    paths = [tmp_path / p for p in ("dist/data/dashboard.json", "data/manifest.json", "dist/data/manifest.json")]
    before = [p.read_bytes() for p in paths]
    build(tmp_path)
    assert before == [p.read_bytes() for p in paths]
