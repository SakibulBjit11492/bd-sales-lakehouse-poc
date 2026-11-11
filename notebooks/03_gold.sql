-- Databricks notebook source
-- 03 Gold: report-ready sales table (division, district, category, season)
CREATE OR REPLACE TABLE sales.gold.fact_sales
CLUSTER BY (OrderDateKey)
AS SELECT f.SalesOrderNumber, f.SalesOrderLineNumber, f.OrderDateKey, f.CustomerKey,
          f.ProductKey, f.PromotionKey, f.PaymentMethod, f.OrderQuantity,
          f.SalesAmount, f.DiscountAmount, f.TaxAmt, f.DeliveryCharge, f.TotalProductCost,
          g.DivisionName, g.District, p.Category, p.Subcategory,
          d.FullDate, d.Year, d.Month, d.EventName
FROM sales.silver.factinternetsales f
JOIN sales.silver.dimcustomer  c ON c.CustomerKey  = f.CustomerKey
JOIN sales.silver.dimgeography g ON g.GeographyKey = c.GeographyKey
JOIN sales.silver.dimproduct   p ON p.ProductKey   = f.ProductKey
JOIN sales.silver.dimdate      d ON d.DateKey      = f.OrderDateKey;

-- COMMAND ----------

-- Quick look: sales by division and year (million BDT)
SELECT DivisionName, Year, ROUND(SUM(SalesAmount) / 1e6, 1) AS sales_m_bdt
FROM sales.gold.fact_sales
GROUP BY ALL
ORDER BY Year, sales_m_bdt DESC;
