# Databricks notebook source
# MAGIC %md
# MAGIC # 04 Validation: SQL Server vs lakehouse
# MAGIC Compares the latest source totals (uploaded by `ingest/extract_upload.py`) with Silver and Gold.
# MAGIC Raises an error on any mismatch, so the Job fails.

# COMMAND ----------

import json
from pyspark.sql import functions as F

ctrl_dir = "/Volumes/sales/bronze/landing/_control/"
latest = sorted(dbutils.fs.ls(ctrl_dir), key=lambda f: f.name)[-1]
src = json.loads(dbutils.fs.head(latest.path))
run, results = src["run"], []

# Row counts: SQL Server vs Silver
for t, expected in src["counts"].items():
    actual = spark.table(f"sales.silver.{t.lower()}").count()
    results.append((run, f"{t} row count", float(expected), float(actual), expected == actual))

# Sales total: SQL Server vs Gold (exact decimal comparison)
from decimal import Decimal
gold = spark.sql("SELECT SUM(SalesAmount) FROM sales.gold.fact_sales").first()[0]
expected = Decimal(str(src["fact_sales_amount"]))
results.append((run, "Total SalesAmount", float(expected), float(gold),
                abs(gold - expected) < Decimal("0.01")))

# Orphans: facts with no matching customer
orphans = spark.sql("""SELECT COUNT(*) FROM sales.silver.factinternetsales f
    LEFT ANTI JOIN sales.silver.dimcustomer c ON f.CustomerKey = c.CustomerKey""").first()[0]
results.append((run, "Facts without customer", 0.0, float(orphans), orphans == 0))

df = (spark.createDataFrame(results,
        "run string, check_name string, expected double, actual double, passed boolean")
        .withColumn("checked_at", F.current_timestamp()))
df.write.mode("append").saveAsTable("sales.audit.validation_results")
display(df)

failed = [r[1] for r in results if not r[4]]
if failed:
    raise Exception(f"Validation failed: {failed}")   # makes the Job fail
