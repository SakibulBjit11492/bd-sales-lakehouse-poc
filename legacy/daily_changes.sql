/* Simulate one day of changes in SalesDW_BD, so incremental loads, MERGE and SCD2 have something
   to pick up. Every changed row gets ModifiedDate = now (the watermark column).
   Run once per "day":  sqlcmd -S localhost -U sa -P <password> -C -i daily_changes.sql            */
USE SalesDW_BD;
SET NOCOUNT ON;

DECLARE @now      DATETIME2(0) = SYSDATETIME();
DECLARE @today    INT = CONVERT(INT, FORMAT(@now, 'yyyyMMdd'));
DECLARE @due      INT = CONVERT(INT, FORMAT(DATEADD(DAY, 5, @now), 'yyyyMMdd'));
DECLARE @ship     INT = CONVERT(INT, FORMAT(DATEADD(DAY, 2, @now), 'yyyyMMdd'));
DECLARE @recent   INT = (SELECT MAX(OrderDateKey) FROM dbo.FactInternetSales) - 10000;  -- last 12 months
DECLARE @maxOrder INT = (SELECT MAX(CAST(SUBSTRING(SalesOrderNumber, 6, 20) AS INT)) FROM dbo.FactInternetSales);

-- 1) New orders: copy 2,000 random recent orders as brand-new orders dated today (INSERTs)
WITH picked AS (
    SELECT TOP (2000) SalesOrderNumber, ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS rn
    FROM (SELECT DISTINCT SalesOrderNumber FROM dbo.FactInternetSales WHERE OrderDateKey >= @recent) o
    ORDER BY NEWID()
)
INSERT INTO dbo.FactInternetSales
SELECT CONCAT('BD-SO', @maxOrder + p.rn), f.SalesOrderLineNumber, @today, @due, @ship,
       f.CustomerKey, f.ProductKey, f.PromotionKey, f.PaymentMethod, f.OrderQuantity, f.UnitPrice,
       f.ExtendedAmount, f.DiscountAmount, f.ProductStandardCost, f.TotalProductCost, f.SalesAmount,
       f.TaxAmt, f.DeliveryCharge, f.CurrencyCode, @now
FROM picked p
JOIN dbo.FactInternetSales f ON f.SalesOrderNumber = p.SalesOrderNumber;
PRINT CONCAT('New order lines: ', @@ROWCOUNT);

-- 2) Corrections: 200 recent order lines get +1 quantity, amounts recalculated (UPDATEs for MERGE)
WITH pick AS (
    SELECT TOP (200) * FROM dbo.FactInternetSales WHERE OrderDateKey >= @recent ORDER BY NEWID()
)
UPDATE f
SET OrderQuantity    = v.qty,
    ExtendedAmount   = v.ext,
    DiscountAmount   = v.disc,
    TotalProductCost = f.ProductStandardCost * v.qty,
    SalesAmount      = v.ext - v.disc,
    TaxAmt           = ROUND((v.ext - v.disc) * 0.15, 2),   -- VAT 15%
    ModifiedDate     = @now
FROM pick f
JOIN dbo.DimPromotion p ON p.PromotionKey = f.PromotionKey
CROSS APPLY (SELECT f.OrderQuantity + 1 AS qty,
                    f.UnitPrice * (f.OrderQuantity + 1) AS ext,
                    ROUND(f.UnitPrice * (f.OrderQuantity + 1) * p.DiscountPct, 2) AS disc) v;
PRINT CONCAT('Corrected order lines: ', @@ROWCOUNT);

-- 3) Customer changes: 500 customers move district (possibly to another division) or change segment (SCD2)
DECLARE @geoCount INT = (SELECT MAX(GeographyKey) FROM dbo.DimGeography);
WITH c AS (SELECT TOP (500) * FROM dbo.DimCustomer ORDER BY NEWID())
UPDATE c
SET CustomerSegment = CASE WHEN ABS(CHECKSUM(NEWID())) % 4 = 0
                           THEN CASE CustomerSegment WHEN 'Individual' THEN 'Small Business' ELSE 'Individual' END
                           ELSE CustomerSegment END,
    GeographyKey    = 1 + ABS(CHECKSUM(NEWID())) % @geoCount,
    ModifiedDate    = @now;
PRINT CONCAT('Changed customers: ', @@ROWCOUNT);

-- 4) Price changes: 10 products get a 5% price rise, rounded to 10 Taka (SCD2 on products)
WITH p AS (SELECT TOP (10) * FROM dbo.DimProduct ORDER BY NEWID())
UPDATE p
SET ListPrice    = ROUND(ListPrice * 1.05, -1),
    StandardCost = ROUND(StandardCost * 1.03, 2),
    ModifiedDate = @now;
PRINT CONCAT('Repriced products: ', @@ROWCOUNT);
