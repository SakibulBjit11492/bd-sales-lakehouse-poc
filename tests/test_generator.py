import subprocess
import sys

import pandas as pd


def test_generator_small(tmp_path):
    out = tmp_path / "data"
    subprocess.run([sys.executable, "legacy/generate_sales_data_bd.py", "--fact-rows", "5000",
                    "--customers", "500", "--products", "50", "--out", str(out)], check=True)
    fact = pd.read_csv(out / "FactInternetSales.csv")
    geo = pd.read_csv(out / "DimGeography.csv")

    assert len(fact) == 5000
    assert len(geo) == 64 and geo["DivisionName"].nunique() == 8
    assert not fact.duplicated(["SalesOrderNumber", "SalesOrderLineNumber"]).any()
    assert fact["CustomerKey"].between(1, 500).all()


def test_generator_is_repeatable(tmp_path):
    for name in ("a", "b"):
        subprocess.run([sys.executable, "legacy/generate_sales_data_bd.py", "--fact-rows", "1000",
                        "--customers", "100", "--products", "20", "--out", str(tmp_path / name)],
                       check=True)
    a = pd.read_csv(tmp_path / "a" / "FactInternetSales.csv")
    b = pd.read_csv(tmp_path / "b" / "FactInternetSales.csv")
    pd.testing.assert_frame_equal(a, b)   # same seed -> same data
