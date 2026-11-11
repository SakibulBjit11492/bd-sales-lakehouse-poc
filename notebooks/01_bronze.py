# Databricks notebook source
# MAGIC %md
# MAGIC # 01 Bronze: landing volume -> Bronze tables (Auto Loader)
# MAGIC Loads only files not seen before (checkpoint). Bronze is append-only and keeps every version.

# COMMAND ----------

base = "/Volumes/sales/bronze/landing"
tables = ["FactInternetSales", "DimCustomer", "DimProduct",
          "DimGeography", "DimDate", "DimPromotion"]

for t in tables:
    (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "parquet")
        .option("cloudFiles.schemaLocation", f"{base}/_schemas/{t}")
        .load(f"{base}/{t}/")
        .selectExpr("*", "current_timestamp() AS _ingested_at",
                    "_metadata.file_path AS _source_file")
        .writeStream
        .option("checkpointLocation", f"{base}/_checkpoints/{t}")
        .trigger(availableNow=True)      # load all new files, then stop
        .toTable(f"sales.bronze.{t.lower()}")
        .awaitTermination())
    print(t, "loaded")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 'fact' AS t, COUNT(*) AS n FROM sales.bronze.factinternetsales UNION ALL
# MAGIC SELECT 'customer', COUNT(*) FROM sales.bronze.dimcustomer UNION ALL
# MAGIC SELECT 'geography', COUNT(*) FROM sales.bronze.dimgeography
