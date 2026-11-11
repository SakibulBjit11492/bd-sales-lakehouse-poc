-- Databricks notebook source
-- One-time setup: catalog, schemas and the landing volume.
-- If CREATE CATALOG is not allowed, use the `workspace` catalog and replace `sales.` everywhere.
CREATE CATALOG IF NOT EXISTS sales;
CREATE SCHEMA IF NOT EXISTS sales.bronze;
CREATE SCHEMA IF NOT EXISTS sales.silver;
CREATE SCHEMA IF NOT EXISTS sales.gold;
CREATE SCHEMA IF NOT EXISTS sales.audit;
CREATE VOLUME IF NOT EXISTS sales.bronze.landing;
