"""
Extract new/changed rows from the legacy SQL Server (SalesDW_BD) and upload them
as Parquet files to the Databricks landing volume.

Run from the repo root:
    export SQL_SA_PASSWORD=...        # never hard-code the password
    python ingest/extract_upload.py
"""
import datetime as dt
import json
import os
import subprocess
import warnings

import pandas as pd
import pyodbc

# pandas warns when given a plain pyodbc connection; it works fine, so hide the noise
warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")

SQL_PWD = os.environ["SQL_SA_PASSWORD"]
CONN = ("DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost,1433;DATABASE=SalesDW_BD;"
        f"UID=sa;PWD={SQL_PWD};TrustServerCertificate=yes")
VOLUME = os.environ.get("LANDING_VOLUME", "dbfs:/Volumes/sales/bronze/landing")
TABLES = {  # table: watermark column (None = full load every run)
    "FactInternetSales": "ModifiedDate", "DimCustomer": "ModifiedDate",
    "DimProduct": "ModifiedDate", "DimGeography": "ModifiedDate",
    "DimDate": None, "DimPromotion": None,
}
WM_FILE = "watermarks.json"


_created_folders = set()


def upload(local, folder):
    # Create the target folder once per run (does nothing if it already exists)
    target_dir = f"{VOLUME}/{folder}"
    if folder not in _created_folders:
        subprocess.run(["databricks", "fs", "mkdir", target_dir], check=True)
        _created_folders.add(folder)
    # Full destination file path, so the CLI never treats the folder name as a file
    dest = f"{target_dir}/{os.path.basename(local)}"
    subprocess.run(["databricks", "fs", "cp", local, dest], check=True)


def main():
    wm = {}
    if os.path.exists(WM_FILE):
        with open(WM_FILE) as f:
            wm = json.load(f)
    run = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    conn = pyodbc.connect(CONN)

    # 1) Extract changed rows and upload them
    for table, col in TABLES.items():
        if col is None:
            sql, params = f"SELECT * FROM dbo.{table}", []
        else:
            sql, params = f"SELECT * FROM dbo.{table} WHERE {col} > ?", [wm.get(table, "1900-01-01")]
        os.makedirs(f"out/{table}", exist_ok=True)
        rows, new_max = 0, wm.get(table)
        for i, chunk in enumerate(pd.read_sql(sql, conn, params=params, chunksize=500_000)):
            local = f"out/{table}/{table}_{run}_{i}.parquet"
            chunk.to_parquet(local, index=False)
            upload(local, table)
            rows += len(chunk)
            if col:
                new_max = max(new_max or "", str(chunk[col].max()))
        if col and rows:
            wm[table] = new_max  # move the watermark only after a successful upload
        print(f"{table}: {rows:,} rows uploaded")

    # 2) Upload source totals for the validation notebook
    cur = conn.cursor()
    counts = {t: cur.execute(f"SELECT COUNT_BIG(*) FROM dbo.{t}").fetchone()[0] for t in TABLES}
    total = float(cur.execute("SELECT SUM(SalesAmount) FROM dbo.FactInternetSales").fetchone()[0])
    os.makedirs("out/_control", exist_ok=True)
    ctrl = f"out/_control/source_{run}.json"
    with open(ctrl, "w") as f:
        json.dump({"run": run, "counts": counts, "fact_sales_amount": total}, f)
    upload(ctrl, "_control")

    with open(WM_FILE, "w") as f:
        json.dump(wm, f, indent=2)
    print("Done. Watermarks:", wm)


if __name__ == "__main__":
    main()