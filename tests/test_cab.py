import numpy as np
import pandas as pd
import pytest

from decision_lab.cab import aggregate_cab, build_forecasts, calendar_features, join_tables, retention_rows


@pytest.mark.parametrize("table", ["cab", "transactions", "customers", "cities"])
def test_duplicate_join_keys_fail(tables, table):
    tables[table] = pd.concat([tables[table], tables[table].iloc[:1]], ignore_index=True)
    with pytest.raises(ValueError, match="Duplicate"):
        join_tables(tables)


@pytest.mark.parametrize("table,field", [("cab", "Price Charged"), ("cab", "Date of Travel"), ("transactions", "Customer ID"), ("customers", "Age"), ("cities", "Population")])
def test_missing_fields_fail(tables, table, field):
    tables[table] = tables[table].drop(columns=field)
    with pytest.raises(ValueError, match="Missing fields"):
        join_tables(tables)


@pytest.mark.parametrize("table,field,value", [
    ("cab", "Price Charged", "bad"), ("cab", "Price Charged", "nan"),
    ("cab", "Cost of Trip", "inf"), ("cab", "Cost of Trip", -1),
    ("cab", "KM Travelled", None), ("cab", "Transaction ID", 1.5),
    ("cab", "Transaction ID", 0), ("cab", "Date of Travel", "2016-01-02"),
    ("cab", "Date of Travel", 42371.5), ("cab", "Date of Travel", 1),
    ("cab", "Date of Travel", 100001), ("cab", "Company", " "),
    ("transactions", "Customer ID", None), ("customers", "Age", 121),
    ("customers", "Income (USD/Month)", -1), ("cities", "Population", "1,00"),
    ("cities", "Users", "NaN"),
])
def test_malformed_values_fail(tables, table, field, value):
    tables[table][field] = tables[table][field].astype(object)
    tables[table].loc[0, field] = value
    with pytest.raises(ValueError):
        join_tables(tables)


def test_left_joins_retain_unmatched_rows(tables):
    tables["transactions"] = tables["transactions"].iloc[1:]
    tables["customers"] = tables["customers"].iloc[2:]
    tables["cities"].loc[0, "City"] = "OTHER CITY"
    rows, audit = join_tables(tables)
    assert len(rows) == audit["retained_rows"] == 36
    assert audit["transactions"]["unmatched_rows"] == 1
    assert audit["customers"]["unmatched_rows"] == 6
    assert audit["cities"]["unmatched_rows"] == 36
    aggregates = aggregate_cab(rows)
    assert sum(s["trips"] for s in aggregates["segments"]) == 36
    assert next(s for s in aggregates["segments"] if s["segment"] == "unknown")["trips"] == 1
    assert aggregates["geography"][0]["population"] is None


def test_aggregates_segments_and_excel_origin(tables):
    rows, audit = join_tables(tables)
    data = aggregate_cab(rows)
    assert rows.iloc[0]["date"] == pd.Timestamp("2016-01-01")
    assert audit["retained_fraction"] == 1
    assert data["companies"][0] == {"company": "Example Cab", "trips": 36, "revenue": 3600.0, "cost": 2340.0, "contribution": 1260.0, "customers": 3}
    assert {r["segment"]: (r["customers"], r["trips"]) for r in data["segments"]} == {"one-trip": (1, 1), "2-5": (1, 5), "6+": (1, 30)}
    assert all("customer_id" not in row and "Gender" not in row for rows in data.values() for row in rows)


def test_negative_contribution_is_not_clipped(tables):
    tables["cab"]["Cost of Trip"] = 120
    rows, _ = join_tables(tables)
    assert aggregate_cab(rows)["companies"][0]["contribution"] == -720


def test_retention_unknown_and_no_future_fill(tables):
    rows, _ = join_tables(tables)
    result = retention_rows(rows)
    assert result[0]["retention_rate"] is None
    assert result[0]["returning_customers"] is None
    assert result[1]["retention_rate"] == 0
    assert result[2]["retention_rate"] == 1
    later_changed = rows.copy()
    later_changed.loc[later_changed["month"] > "2016-06", "customer_id"] = 999
    assert retention_rows(later_changed)[:6] == result[:6]
    gap = rows[rows["month"] != "2016-02"]
    assert retention_rows(gap)[2]["retention_rate"] is None


def test_ridge_and_baseline_do_not_use_holdout_targets(tables):
    rows, _ = join_tables(tables)
    monthly = rows.groupby(["company", "month"])[["revenue"]].sum().reset_index()
    original = build_forecasts(monthly)
    monthly.loc[monthly["month"] >= "2018-07", "revenue"] = 1e12
    changed = build_forecasts(monthly)
    for before, after in zip(original, changed):
        assert [p["predicted"] for p in before["points"]] == [p["predicted"] for p in after["points"]]
        assert before["mae"] != after["mae"]


def test_scaler_is_fitted_only_on_training(monkeypatch, tables):
    from sklearn.preprocessing import StandardScaler

    original = StandardScaler.fit
    observed = []

    def spy(self, x, *args, **kwargs):
        observed.append(x.copy())
        return original(self, x, *args, **kwargs)

    monkeypatch.setattr(StandardScaler, "fit", spy)
    rows, _ = join_tables(tables)
    aggregate_cab(rows)
    assert len(observed) == 1
    np.testing.assert_array_equal(observed[0], calendar_features(36)[:30])


def test_forecast_rejects_missing_month(tables):
    rows, _ = join_tables(tables)
    with pytest.raises(ValueError, match="36 consecutive"):
        aggregate_cab(rows[rows["month"] != "2017-02"])
