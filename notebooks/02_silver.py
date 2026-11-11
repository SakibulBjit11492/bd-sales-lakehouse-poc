# Databricks notebook source
# MAGIC %md
# MAGIC # 02 Silver: Bronze -> Silver (latest version per key, MERGE)

# COMMAND ----------

from delta.tables import DeltaTable
from pyspark.sql import functions as F, Window

KEYS = {
    "factinternetsales": ["SalesOrderNumber", "SalesOrderLineNumber"],
    "dimcustomer": ["CustomerKey"], "dimproduct": ["ProductKey"],
    "dimgeography": ["GeographyKey"], "dimdate": ["DateKey"],
    "dimpromotion": ["PromotionKey"],
}

for t, keys in KEYS.items():
    src = spark.table(f"sales.bronze.{t}").drop("_source_file")
    newest_first = Window.partitionBy(*keys).orderBy(F.col("_ingested_at").desc())
    src = (src.withColumn("_rn", F.row_number().over(newest_first))
              .filter("_rn = 1").drop("_rn"))

    target = f"sales.silver.{t}"
    if not spark.catalog.tableExists(target):
        src.write.saveAsTable(target)          # first run: create the table
        print(t, "created")
        continue
    cond = " AND ".join(f"t.{k} = s.{k}" for k in keys)
    (DeltaTable.forName(spark, target).alias("t")
        .merge(src.alias("s"), cond)
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute())
    print(t, "merged")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS fact_rows, ROUND(SUM(SalesAmount), 2) AS sales_bdt
# MAGIC FROM sales.silver.factinternetsales
