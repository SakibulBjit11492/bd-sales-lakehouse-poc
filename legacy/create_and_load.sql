/* Create the legacy SalesDW_BD database and bulk-load the synthetic Bangladesh CSVs.
   Run with:  sqlcmd -S localhost -U sa -P <password> -C -v DataDir="/var/opt/mssql/import" -i create_and_load.sql
   DataDir = folder (as seen by SQL Server) that holds the CSV files. Amounts are in BDT. */

IF DB_ID('SalesDW_BD') IS NULL CREATE DATABASE SalesDW_BD;
GO
USE SalesDW_BD;
GO

DROP TABLE IF EXISTS dbo.FactInternetSales, dbo.DimDate, dbo.DimGeography,
                     dbo.DimCustomer, dbo.DimProduct, dbo.DimPromotion;
GO

CREATE TABLE dbo.DimDate (
    DateKey INT NOT NULL PRIMARY KEY, FullDate DATE NOT NULL, [Year] SMALLINT, [Quarter] TINYINT,
    [Month] TINYINT, MonthName NVARCHAR(10), DayOfMonth TINYINT, DayOfWeek TINYINT,
    DayName NVARCHAR(10), IsWeekend BIT,              -- Friday and Saturday
    EventName NVARCHAR(30) NULL);                     -- Eid, Pohela Boishakh, 11.11, ...

CREATE TABLE dbo.DimGeography (
    GeographyKey INT NOT NULL PRIMARY KEY, District NVARCHAR(50) NOT NULL, DivisionName NVARCHAR(30) NOT NULL,
    CountryRegionName NVARCHAR(30), IsDivisionalHQ BIT, ModifiedDate DATETIME2(0) NOT NULL);

CREATE TABLE dbo.DimCustomer (
    CustomerKey INT NOT NULL PRIMARY KEY, CustomerAlternateKey NVARCHAR(15) NOT NULL,
    FirstName NVARCHAR(50), LastName NVARCHAR(50), Gender NCHAR(1), BirthDate DATE,
    EmailAddress NVARCHAR(100), CustomerSegment NVARCHAR(20), GeographyKey INT,
    ModifiedDate DATETIME2(0) NOT NULL);

CREATE TABLE dbo.DimProduct (
    ProductKey INT NOT NULL PRIMARY KEY, ProductAlternateKey NVARCHAR(25) NOT NULL,
    ProductName NVARCHAR(60), Category NVARCHAR(30), Subcategory NVARCHAR(30), Variant NVARCHAR(20),
    StandardCost MONEY, ListPrice MONEY, ModifiedDate DATETIME2(0) NOT NULL);

CREATE TABLE dbo.DimPromotion (
    PromotionKey INT NOT NULL PRIMARY KEY, PromotionName NVARCHAR(50), DiscountPct DECIMAL(5,2));

CREATE TABLE dbo.FactInternetSales (
    SalesOrderNumber NVARCHAR(20) NOT NULL, SalesOrderLineNumber TINYINT NOT NULL,
    OrderDateKey INT NOT NULL, DueDateKey INT NOT NULL, ShipDateKey INT NOT NULL,
    CustomerKey INT NOT NULL, ProductKey INT NOT NULL, PromotionKey INT NOT NULL,
    PaymentMethod NVARCHAR(20) NOT NULL, OrderQuantity SMALLINT NOT NULL,
    UnitPrice MONEY, ExtendedAmount MONEY, DiscountAmount MONEY, ProductStandardCost MONEY,
    TotalProductCost MONEY, SalesAmount MONEY, TaxAmt MONEY, DeliveryCharge MONEY,
    CurrencyCode CHAR(3) NOT NULL, ModifiedDate DATETIME2(0) NOT NULL);
GO

BULK INSERT dbo.DimDate           FROM '$(DataDir)/DimDate.csv'           WITH (FORMAT = 'CSV', FIRSTROW = 2, TABLOCK);
BULK INSERT dbo.DimGeography      FROM '$(DataDir)/DimGeography.csv'      WITH (FORMAT = 'CSV', FIRSTROW = 2, TABLOCK);
BULK INSERT dbo.DimCustomer       FROM '$(DataDir)/DimCustomer.csv'       WITH (FORMAT = 'CSV', FIRSTROW = 2, TABLOCK);
BULK INSERT dbo.DimProduct        FROM '$(DataDir)/DimProduct.csv'        WITH (FORMAT = 'CSV', FIRSTROW = 2, TABLOCK);
BULK INSERT dbo.DimPromotion      FROM '$(DataDir)/DimPromotion.csv'      WITH (FORMAT = 'CSV', FIRSTROW = 2, TABLOCK);
BULK INSERT dbo.FactInternetSales FROM '$(DataDir)/FactInternetSales.csv' WITH (FORMAT = 'CSV', FIRSTROW = 2, TABLOCK, BATCHSIZE = 1000000);
GO

UPDATE dbo.DimDate SET EventName = NULL WHERE EventName = '';
ALTER TABLE dbo.FactInternetSales
    ADD CONSTRAINT PK_FactInternetSales PRIMARY KEY CLUSTERED (SalesOrderNumber, SalesOrderLineNumber);
CREATE INDEX IX_Fact_ModifiedDate ON dbo.FactInternetSales (ModifiedDate);   -- watermark extracts
CREATE INDEX IX_Fact_OrderDateKey ON dbo.FactInternetSales (OrderDateKey);
CREATE INDEX IX_Customer_ModifiedDate ON dbo.DimCustomer (ModifiedDate);
CREATE INDEX IX_Product_ModifiedDate ON dbo.DimProduct (ModifiedDate);
GO

-- Baseline numbers for the validation step
SELECT 'FactInternetSales' AS TableName, COUNT_BIG(*) AS [Rows], SUM(SalesAmount) AS SalesAmountBDT FROM dbo.FactInternetSales
UNION ALL SELECT 'DimCustomer', COUNT_BIG(*), NULL FROM dbo.DimCustomer
UNION ALL SELECT 'DimProduct',  COUNT_BIG(*), NULL FROM dbo.DimProduct
UNION ALL SELECT 'DimGeography', COUNT_BIG(*), NULL FROM dbo.DimGeography;

-- Sales by division
SELECT g.DivisionName, SUM(f.SalesAmount) AS SalesAmountBDT
FROM dbo.FactInternetSales f
JOIN dbo.DimCustomer c  ON c.CustomerKey = f.CustomerKey
JOIN dbo.DimGeography g ON g.GeographyKey = c.GeographyKey
GROUP BY g.DivisionName ORDER BY SalesAmountBDT DESC;
GO
