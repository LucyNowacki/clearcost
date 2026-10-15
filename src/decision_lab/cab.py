"""Strict CAB ingestion, lossless joins and non-demographic aggregates."""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .metrics import regression_metrics

FIELDS = {
    "cab": ("Transaction ID", "Date of Travel", "Company", "City", "KM Travelled", "Price Charged", "Cost of Trip"),
    "transactions": ("Transaction ID", "Customer ID", "Payment_Mode"),
    "customers": ("Customer ID", "Gender", "Age", "Income (USD/Month)"),
    "cities": ("City", "Population", "Users"),
}
FILENAMES = {"cab": "Cab_Data.csv", "transactions": "Transaction_ID.csv", "customers": "Customer_ID.csv", "cities": "City.csv"}
SEGMENTS = ("one-trip", "2-5", "6+")


def _number(series, field, *, integer=False, minimum=0, maximum=None):
    try:
        result = pd.to_numeric(series, errors="raise")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric field: {field}") from exc
    if result.isna().any() or not np.isfinite(result.to_numpy(dtype=float)).all():
        raise ValueError(f"Missing or nonfinite numeric field: {field}")
    if (result < minimum).any() or (maximum is not None and (result > maximum).any()):
        raise ValueError(f"Out-of-range numeric field: {field}")
    if integer:
        if (result % 1 != 0).any():
            raise ValueError(f"Nonintegral field: {field}")
        return result.astype("int64")
    return result.astype(float)


def _unique(frame, key, table):
    if frame[key].duplicated().any():
        raise ValueError(f"Duplicate {key} in {table}; join cardinality is not safe")


def validate_tables(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    validated = {}
    for name, fields in FIELDS.items():
        if name not in tables:
            raise ValueError(f"Missing table: {name}")
        missing = set(fields) - set(tables[name].columns)
        if missing:
            raise ValueError(f"Missing fields in {name}: {sorted(missing)}")
        frame = tables[name].loc[:, list(fields)].copy()
        for key in set(fields) & {"Transaction ID", "Customer ID"}:
            frame[key] = _number(frame[key], key, integer=True, minimum=1, maximum=2**53 - 1)
        for key in set(fields) & {"City", "Company", "Gender", "Payment_Mode"}:
            if frame[key].isna().any():
                raise ValueError(f"Missing field: {name}.{key}")
            frame[key] = frame[key].astype(str).str.strip()
            if frame[key].eq("").any():
                raise ValueError(f"Blank field: {name}.{key}")
        unique_key = {"cab": "Transaction ID", "transactions": "Transaction ID", "customers": "Customer ID", "cities": "City"}[name]
        _unique(frame, unique_key, name)
        validated[name] = frame
    cab = validated["cab"]
    if cab.empty:
        raise ValueError("Cab data is empty")
    for key in ("Price Charged", "Cost of Trip", "KM Travelled"):
        cab[key] = _number(cab[key], key)
    serial = _number(cab["Date of Travel"], "Date of Travel", integer=True, minimum=1, maximum=100000)
    cab["date"] = pd.to_datetime(serial, unit="D", origin="1899-12-30")
    if not cab["date"].between("2016-01-01", "2018-12-31").all():
        raise ValueError("Date of Travel is outside the documented 2016-2018 CAB window")
    customers = validated["customers"]
    customers["Age"] = _number(customers["Age"], "Age", integer=True, maximum=120)
    customers["Income (USD/Month)"] = _number(customers["Income (USD/Month)"], "Income (USD/Month)")
    for key in ("Population", "Users"):
        strings = validated["cities"][key].astype(str).str.strip()
        if not strings.str.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)").all():
            raise ValueError(f"Malformed city numeric field: {key}")
        validated["cities"][key] = _number(strings.str.replace(",", "", regex=False), key, integer=True)
    return validated


def join_tables(tables: dict[str, pd.DataFrame]):
    tables = validate_tables(tables)
    joined = tables["cab"].copy()
    audit = {"cab_rows": len(joined)}
    for name, key, columns in (
        ("transactions", "Transaction ID", ["Transaction ID", "Customer ID"]),
        ("customers", "Customer ID", ["Customer ID"]),
        ("cities", "City", ["City", "Population", "Users"]),
    ):
        right = tables[name][columns]
        before = len(joined)
        unmatched_right = int((~right[key].isin(joined[key])).sum())
        joined = joined.merge(right, on=key, how="left", validate="many_to_one", indicator=True, sort=False)
        unmatched = int(joined["_merge"].eq("left_only").sum())
        audit[name] = {
            "relationship": "many_to_one",
            "left_rows": before,
            "right_rows": len(right),
            "output_rows": len(joined),
            "matched_rows": before - unmatched,
            "unmatched_rows": unmatched,
            "unused_right_rows": unmatched_right,
        }
        joined = joined.drop(columns="_merge")
        if len(joined) != before:
            raise ValueError(f"Row retention failure joining {name}")
    joined = joined.rename(columns={"Company": "company", "City": "city", "Customer ID": "customer_id", "Price Charged": "revenue", "Cost of Trip": "cost"})
    joined["month"] = joined["date"].dt.to_period("M").astype(str)
    joined["contribution"] = joined["revenue"] - joined["cost"]
    audit["retained_rows"] = len(joined)
    audit["retained_fraction"] = len(joined) / audit["cab_rows"]
    audit["missing_customer_id_rows"] = int(joined["customer_id"].isna().sum())
    return joined, audit


def load_cab(raw: Path):
    return join_tables({name: pd.read_csv(raw / filename, dtype=str) for name, filename in FILENAMES.items()})


def _records(frame: pd.DataFrame) -> list[dict]:
    return frame.astype(object).where(frame.notna(), None).to_dict("records")


def retention_rows(cab: pd.DataFrame) -> list[dict]:
    """Previous-calendar-month overlap; the first month has no denominator."""
    months = pd.period_range(cab["month"].min(), cab["month"].max(), freq="M").astype(str)
    rows = []
    for company, group in cab.groupby("company", sort=True):
        by_month = group.groupby("month")["customer_id"].agg(lambda x: set(x.dropna()))
        previous = None
        for month in months:
            current = by_month.get(month, set())
            returning = len(current & previous) if previous is not None else None
            rows.append({
                "company": company, "month": month, "customers": len(current),
                "previous_month_customers": len(previous) if previous is not None else None,
                "returning_customers": returning,
                "retention_rate": returning / len(previous) if previous else None,
            })
            previous = current
    return rows


def aggregate_cab(cab: pd.DataFrame) -> dict:
    aggregation = {"trips": ("revenue", "size"), "revenue": ("revenue", "sum"), "cost": ("cost", "sum"), "contribution": ("contribution", "sum")}
    monthly = cab.groupby(["month", "company", "city"], sort=True).agg(**aggregation).reset_index()
    companies = cab.groupby("company", sort=True).agg(**aggregation, customers=("customer_id", "nunique")).reset_index()
    geography = cab.groupby("city", sort=True).agg(**aggregation, population=("Population", "first"), source_users=("Users", "first")).reset_index()
    known = cab[cab["customer_id"].notna()]
    customers = known.groupby(["company", "customer_id"], sort=True).agg(**aggregation).reset_index()
    customers["segment"] = np.select([customers["trips"] == 1, customers["trips"] <= 5], ["one-trip", "2-5"], default="6+")
    segments = customers.groupby(["company", "segment"], sort=True).agg(customers=("customer_id", "size"), trips=("trips", "sum"), revenue=("revenue", "sum"), contribution=("contribution", "sum"))
    index = pd.MultiIndex.from_product([companies["company"], SEGMENTS], names=["company", "segment"])
    segments = segments.reindex(index, fill_value=0).reset_index()
    unknown = cab[cab["customer_id"].isna()].groupby("company").agg(**aggregation).reset_index()
    if not unknown.empty:
        unknown["segment"], unknown["customers"] = "unknown", 0
        segments = pd.concat([segments, unknown.drop(columns="cost")], ignore_index=True)
    return {"monthly": _records(monthly), "companies": _records(companies), "segments": _records(segments), "geography": _records(geography), "retention": retention_rows(cab), "forecast": build_forecasts(monthly)}


def calendar_features(length: int) -> np.ndarray:
    t = np.arange(length, dtype=float)
    return np.column_stack([t] + [function(2 * np.pi * k * t / 12) for k in (1, 2) for function in (np.sin, np.cos)])


def build_forecasts(monthly: pd.DataFrame) -> list[dict]:
    """One fixed-origin six-month revenue holdout; no holdout-driven selection."""
    rows = []
    for company, data in monthly.groupby("company", sort=True):
        revenue = data.groupby("month")["revenue"].sum().sort_index()
        months = pd.period_range(revenue.index.min(), revenue.index.max(), freq="M").astype(str)
        if len(months) != 36 or list(revenue.index) != list(months):
            raise ValueError(f"Expected 36 consecutive observed months for {company}")
        y = revenue.to_numpy(dtype=float)
        features = calendar_features(36)
        model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
        model.fit(features[:30], y[:30])
        predictions = {"Ridge trend + seasonality": model.predict(features[30:]), "Seasonal naive": y[18:24]}
        for name, predicted in predictions.items():
            rows.append({
                "company": company, "model": name, "target": "monthly revenue", "currency": "USD",
                "model_name": "ridge" if name.startswith("Ridge") else "seasonal_naive",
                "model_label": name,
                **regression_metrics(y[30:], predicted),
                "train_end": months[29], "test_start": months[30], "test_end": months[35],
                "train_months": 30, "holdout_months": 6,
                "points": [{"month": month, "actual": float(actual), "predicted": float(pred)} for month, actual, pred in zip(months[30:], y[30:], predicted)],
            })
    return rows
