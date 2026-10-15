import pandas as pd
import pytest


@pytest.fixture
def tables():
    months = pd.date_range("2016-01-01", periods=36, freq="MS")
    ids = list(range(1, 37))
    return {
        "cab": pd.DataFrame({
            "Transaction ID": ids,
            "Date of Travel": (months - pd.Timestamp("1899-12-30")).days,
            "Company": ["Example Cab"] * 36, "City": ["EXAMPLE CITY"] * 36,
            "KM Travelled": [10] * 36, "Price Charged": [100] * 36, "Cost of Trip": [65] * 36,
        }),
        "transactions": pd.DataFrame({"Transaction ID": ids, "Customer ID": [111] + [222] * 5 + [333] * 30, "Payment_Mode": ["Card"] * 36}),
        "customers": pd.DataFrame({"Customer ID": [111, 222, 333], "Gender": ["Female", "Male", "Female"], "Age": [30, 40, 50], "Income (USD/Month)": [2000, 3000, 4000]}),
        "cities": pd.DataFrame({"City": ["EXAMPLE CITY"], "Population": [" 10,000 "], "Users": ["1,000"]}),
    }
