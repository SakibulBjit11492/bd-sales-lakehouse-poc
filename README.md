# BD Sales Lakehouse PoC

Migrates a legacy on-prem SQL Server sales warehouse (synthetic Bangladesh e-commerce data: 8 divisions,
64 districts, amounts in BDT) to a Databricks lakehouse with Bronze, Silver and Gold layers.

```text
SQL Server (Docker) -> ingest/extract_upload.py -> landing volume -> Bronze (Auto Loader)
                    -> Silver (MERGE) -> Gold -> dashboard
```

## Repo layout

| Path | What it is |
| --- | --- |
| `legacy/` | Synthetic data generator and SQL Server scripts (load, daily changes) |
| `ingest/extract_upload.py` | Incremental extract from SQL Server, upload to Databricks |
| `notebooks/` | Databricks notebooks: setup, Bronze, Silver, Gold, validation |
| `databricks.yml` | Asset Bundle: the daily job as code |
| `tests/` | Tests for the generator (run in CI) |
| `.github/workflows/ci-cd.yml` | Lint + test on every PR; deploy to Databricks on merge to `main` |

## Prerequisites

Docker Desktop, Python 3.10+, ODBC Driver 18 for SQL Server, Databricks CLI, a Databricks Free Edition workspace.

**Apple Silicon Macs:** turn on Rosetta emulation in Docker Desktop (Settings → General) and add
`--platform linux/amd64` to `docker run`. If pyodbc reports that OpenSSL could not be loaded:

```bash
brew install openssl@3
ln -sfn "$(brew --prefix openssl@3)" /opt/homebrew/opt/openssl
```

## Quick start (run everything from the repo root)

```bash
# 1. Python environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export SQL_SA_PASSWORD=<your-password>      # or: set -a; source .env; set +a

# 2. Legacy SQL Server with synthetic data
python legacy/generate_sales_data_bd.py --fact-rows 100000 --customers 10000 --out data
docker run -d --platform linux/amd64 --name legacy-sql -p 1433:1433 -e ACCEPT_EULA=Y \
  -e MSSQL_PID=Developer -e MSSQL_SA_PASSWORD="$SQL_SA_PASSWORD" mcr.microsoft.com/mssql/server:2022-latest
docker exec -u 0 legacy-sql mkdir -p /var/opt/mssql/import
docker cp data/. legacy-sql:/var/opt/mssql/import/
docker cp legacy/create_and_load.sql legacy-sql:/var/opt/mssql/import/
docker cp legacy/daily_changes.sql legacy-sql:/var/opt/mssql/import/
docker exec -it legacy-sql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$SQL_SA_PASSWORD" -C \
  -v DataDir="/var/opt/mssql/import" -i /var/opt/mssql/import/create_and_load.sql

# 3. Databricks: log in, then run notebooks/00_setup.sql once in the workspace
databricks auth login --host https://<your-workspace>.cloud.databricks.com

# 4. Extract and upload
python ingest/extract_upload.py

# 5. Deploy and run the daily job
databricks bundle validate
databricks bundle deploy
databricks bundle run bd_sales_daily
```

## Simulate a day of changes

```bash
docker exec -it legacy-sql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$SQL_SA_PASSWORD" -C \
  -i /var/opt/mssql/import/daily_changes.sql
python ingest/extract_upload.py
databricks bundle run bd_sales_daily
```

Only the changed rows are uploaded; the validation task checks that the lakehouse matches SQL Server.

## CI/CD

Add two repository secrets in GitHub (Settings → Secrets and variables → Actions):

| Secret | Value |
| --- | --- |
| `DATABRICKS_HOST` | `https://<your-workspace>.cloud.databricks.com` |
| `DATABRICKS_TOKEN` | A Databricks personal access token (Settings → Developer → Access tokens) |

Every pull request runs `ruff` and `pytest`. Every merge to `main` also runs `databricks bundle deploy`.

## Local checks

```bash
pip install pytest ruff
ruff check .
pytest -q
```

## Never commit

Passwords, tokens, `.env`, generated data (`data/`, `out/`, `*.csv`, `*.parquet`) or `watermarks.json`.
All are covered by `.gitignore`.
