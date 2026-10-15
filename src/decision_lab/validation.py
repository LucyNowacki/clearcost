"""Publication-boundary checks for aggregate-only dashboard JSON."""

import math
import re

import numpy as np
import pandas as pd

from .metrics import regression_metrics


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _finite(value):
    if isinstance(value, dict):
        for child in value.values():
            _finite(child)
    elif isinstance(value, list):
        for child in value:
            _finite(child)
    elif isinstance(value, float):
        _require(math.isfinite(value), "Nonfinite JSON value")


def validate_dashboard(payload: dict) -> None:
    """Fail closed before writing output; never export raw CAB identifiers."""
    _finite(payload)
    _require({"meta", "cab", "media"} <= set(payload), "Missing top-level contract")
    meta, cab, media = payload["meta"], payload["cab"], payload["media"]
    _require({"cab_source_url", "cab_commit", "source_notebook_url", "currency", "date_start", "date_end", "row_count", "city_count", "join_audit", "model_notes"} <= set(meta), "Missing metadata")
    _require(meta["currency"] == "USD", "CAB currency must be USD")
    _require(re.fullmatch(r"[a-f0-9]{40}", meta["cab_commit"]) is not None, "Unpinned CAB commit")
    dates = pd.to_datetime([meta["date_start"], meta["date_end"]], format="%Y-%m-%d", errors="raise")
    _require(dates[0] <= dates[1], "Reversed source dates")
    # Explicit allowlists prevent an accidental groupby change leaking identifiers.
    row_fields = {
        "monthly": {"month", "company", "city", "trips", "revenue", "cost", "contribution"},
        "companies": {"company", "trips", "revenue", "cost", "contribution", "customers"},
        "segments": {"company", "segment", "customers", "trips", "revenue", "contribution"},
        "geography": {"city", "trips", "revenue", "cost", "contribution", "population", "source_users"},
        "retention": {"company", "month", "customers", "previous_month_customers", "returning_customers", "retention_rate"},
    }
    _require(set(cab) == {*row_fields, "forecast"}, "Unexpected CAB section")
    for name, allowed in row_fields.items():
        for row in cab[name]:
            _require(set(row) == allowed, f"Missing or unexpected fields in {name}")
            if "trips" in row:
                _require(isinstance(row["trips"], int) and row["trips"] >= 0, "Invalid trip count")
            if "cost" in row:
                _require(math.isclose(row["revenue"] - row["cost"], row["contribution"], abs_tol=0.011), "Contribution must equal revenue minus cost")
    _require(sum(r["trips"] for r in cab["monthly"]) == meta["row_count"], "Monthly aggregation lost rows")
    _require(len({r["city"] for r in cab["monthly"]}) == meta["city_count"], "City count mismatch")
    keys = [(r["month"], r["company"], r["city"]) for r in cab["monthly"]]
    _require(len(keys) == len(set(keys)), "Duplicate monthly aggregate")
    for month, _, _ in keys:
        _require(re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month) is not None, "Malformed aggregate month")
    for company in cab["companies"]:
        for section in ("monthly", "segments"):
            children = [r for r in cab[section] if r["company"] == company["company"]]
            _require(sum(r["trips"] for r in children) == company["trips"], f"{section} lost company rows")
            for key in ("revenue", "contribution"):
                _require(math.isclose(sum(r[key] for r in children), company[key], abs_tol=0.02), f"{section} financial totals differ")
    for row in cab["retention"]:
        rate = row["retention_rate"]
        _require(rate is None or 0 <= rate <= 1, "Invalid retention fraction")
    audit = meta["join_audit"]
    _require(audit["retained_rows"] == audit["cab_rows"] == meta["row_count"], "Join row loss")
    for name in ("transactions", "customers", "cities"):
        row = audit[name]
        _require(row["left_rows"] == row["output_rows"] == meta["row_count"], "Join row loss")
        _require(row["matched_rows"] + row["unmatched_rows"] == row["output_rows"], "Join audit does not reconcile")
    _require(len(cab["forecast"]) == 2 * len(cab["companies"]), "Expected two forecast models per company")
    for forecast in cab["forecast"]:
        points = forecast["points"]
        _require(len(points) == 6 and forecast["train_end"] < forecast["test_start"] <= forecast["test_end"], "Invalid CAB holdout")
        _require(points[0]["month"] == forecast["test_start"] and points[-1]["month"] == forecast["test_end"], "Forecast date mismatch")
        expected = regression_metrics([p["actual"] for p in points], [p["predicted"] for p in points])
        for key, value in expected.items():
            _require(forecast[key] == value, "CAB model metric mismatch")
    _require(media["synthetic"] is True and media["currency"] == "GBP", "Synthetic/real currency boundary violated")
    _require({c["id"] for c in media["channels"]} == {"search", "social", "video"}, "Wrong channels")
    for channel in media["channels"]:
        _require(0 <= channel["decay"] < 1 and channel["half_saturation"] > 0 and channel["coefficient"] >= 0, "Invalid media parameters")
        _require("steady_state_multiplier" in channel, "Missing steady-state multiplier")
        _require(math.isclose(channel["steady_state_multiplier"], 1 / (1 - channel["decay"]), rel_tol=1e-12), "Incorrect steady-state multiplier for unnormalised adstock")
    weekly = media["weekly"]
    _require(len(weekly) == 156, "Expected 156 synthetic weeks")
    _require([r["split"] for r in weekly] == ["train"] * 130 + ["test"] * 26, "Invalid chronological media split")
    week_dates = pd.to_datetime([r["week"] for r in weekly], format="%Y-%m-%d", errors="raise")
    _require((np.diff(week_dates.values) == np.timedelta64(7, "D")).all(), "Nonconsecutive media dates")
    metrics = media["metrics"]
    _require(metrics["holdout_weeks"] == 26 and metrics["train_weeks"] == 130, "Incorrect holdout metadata")
    for model, field in (("model", "predicted"), ("baseline", "baseline_predicted")):
        expected = regression_metrics([r["revenue"] for r in weekly[130:]], [r[field] for r in weekly[130:]])
        for key in ("mae", "rmse"):
            _require(metrics[f"{model}_{key}"] == expected[key], "Media model metric mismatch")
    _require([p["budget"] for p in media["plans"]] == list(range(10000, 100001, 5000)), "Incorrect budget grid")
    for plan in media["plans"]:
        _require(set(plan["shares"]) == {"search", "social", "video"}, "Invalid budget channels")
        shares = list(plan["shares"].values())
        _require(abs(sum(shares) - 1) < 1e-8 and all(0.1 - 1e-8 <= s <= 0.6 + 1e-8 for s in shares), "Infeasible budget shares")
        _require(plan["incremental_revenue"] >= plan["balanced_revenue"] - 1e-6 >= 0, "Budget response failed baseline check")
        optimized, balanced = 0.0, 0.0
        for channel in media["channels"]:
            x = plan["budget"] * plan["shares"][channel["id"]] * channel["steady_state_multiplier"]
            optimized += channel["coefficient"] * (x / (channel["half_saturation"] + x))
            equal_x = plan["budget"] / 3 * channel["steady_state_multiplier"]
            balanced += channel["coefficient"] * (equal_x / (channel["half_saturation"] + equal_x))
        _require(math.isclose(plan["incremental_revenue"], optimized, abs_tol=1e-8), "Optimizer/browser response mismatch")
        _require(math.isclose(plan["balanced_revenue"], balanced, abs_tol=1e-8), "Equal-split/browser response mismatch")
