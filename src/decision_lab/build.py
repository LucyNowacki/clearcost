"""Deterministic local build. No publication, live AI calls or raw-row export."""

import json
from pathlib import Path
import platform

import numpy as np
import pandas as pd
import scipy
import sklearn

from .cab import aggregate_cab, load_cab
from .media import build_media
from .sources import CAB_COMMIT, CAB_SOURCE_URL, NOTEBOOK_COMMIT, NOTEBOOK_URL, fetch_sources, sha256, write_json
from .validation import validate_dashboard

MODEL_NOTES = [
    "CAB is a public teaching dataset, not verified operating records of an actual business. USD is the reporting convention; no currency conversion is performed.",
    "Date of Travel is interpreted as an Excel serial day with origin 1899-12-30, restricted to 2016-2018. The source notebook uses 1900-01-01 and would shift these dates forward by two days.",
    "All CAB transaction rows are retained using many-to-one left joins. Duplicate right keys fail validation; unmatched and unused-right counts are reported separately.",
    "Gross contribution = Price Charged - Cost of Trip. It excludes overhead, tax, financing and other unobserved costs; it is not net profit or an investment return.",
    "Segments are full-window per-company behavioural trip counts: one-trip, 2-5, 6+. They are descriptive, not prospective labels; demographics are never exported or used for targeting.",
    "Customers are unique within each company; customers using both companies appear in both totals. Missing transaction customer IDs remain an explicit unknown segment rather than causing row loss.",
    "Monthly retention is overlap with the preceding calendar month's observed customer IDs divided by that previous month's customer count. Initial or empty-denominator retention is null, never forecast-filled.",
    "Company monthly revenue has 36 observed months. First 30 train, final 6 test; Ridge(alpha=1) uses standardized time trend and two annual Fourier pairs, with scaling fitted only on training months.",
    "Seasonal naive repeats revenue from the same month one year earlier. All baseline inputs precede the holdout origin. MAE/RMSE are USD and WAPE is a fraction; no model or hyperparameter is selected using test errors.",
    "This is a new bounded analysis, not a reproduction of the notebook's UMAP/XGBoost/Prophet forecasts or investment returns. The six-month retrospective holdout is not a future production forecast.",
    "Geography contains city-level aggregates and the source lookup's population/users, with no external geocoding. Lookup values are unverified teaching-data figures, not current census or market penetration estimates.",
]


def build(root: Path, *, allow_download=False) -> dict:
    source_manifest = fetch_sources(root, allow_download=allow_download)
    cab_rows, audit = load_cab(root / "data" / "raw")
    payload = {
        "meta": {
            "cab_source_url": CAB_SOURCE_URL, "cab_commit": CAB_COMMIT,
            "source_notebook_url": NOTEBOOK_URL, "currency": "USD",
            "date_start": cab_rows["date"].min().strftime("%Y-%m-%d"),
            "date_end": cab_rows["date"].max().strftime("%Y-%m-%d"),
            "row_count": len(cab_rows), "city_count": int(cab_rows["city"].nunique()),
            "join_audit": audit, "model_notes": MODEL_NOTES, "schema_version": "1.0",
        },
        "cab": aggregate_cab(cab_rows), "media": build_media(),
    }
    validate_dashboard(payload)
    destination = root / "dist" / "data" / "dashboard.json"
    write_json(destination, payload)
    manifest = {
        "schema_version": "1.0", "source": source_manifest,
        "notebook": {"url": NOTEBOOK_URL, "commit": NOTEBOOK_COMMIT, "role": "historical inspiration, not a reproduced analysis"},
        "artifact": {"path": "dist/data/dashboard.json", "sha256": sha256(destination), "bytes": destination.stat().st_size,
                     "cab_rows": len(cab_rows), "monthly_aggregate_rows": len(payload["cab"]["monthly"]),
                     "raw_customer_rows_exported": False, "synthetic_weeks": 156},
        "runtime": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__, "scikit_learn": sklearn.__version__},
    }
    notebook = root.parent / "references" / "CAB_EDA" / "Cab_2.ipynb"
    if notebook.exists():
        manifest["notebook"].update(sha256=sha256(notebook), cells=len(json.loads(notebook.read_text(encoding="utf-8"))["cells"]))
    write_json(root / "data" / "manifest.json", manifest)
    write_json(root / "dist" / "data" / "manifest.json", manifest)
    return payload


def summary(payload: dict) -> dict:
    return {"row_count": payload["meta"]["row_count"], "date_start": payload["meta"]["date_start"],
            "date_end": payload["meta"]["date_end"], "city_count": payload["meta"]["city_count"],
            "join_audit": payload["meta"]["join_audit"], "companies": payload["cab"]["companies"],
            "forecast": [{k: v for k, v in row.items() if k != "points"} for row in payload["cab"]["forecast"]],
            "media_metrics": payload["media"]["metrics"], "example_plan": payload["media"]["plans"][6]}
