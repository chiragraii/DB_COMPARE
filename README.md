# PostgreSQL schema compare & sync (PK/FK) CLI

Compare schema metadata between two PostgreSQL databases (or mock fixtures) and optionally **add missing primary keys / foreign keys** to the target database.

## Features

- Connect to two PostgreSQL servers via `.env`, environment variables, or CLI flags
- Compare: tables, columns (type + nullability), primary keys, foreign keys, unique constraints, check constraints, indexes, sequences
- Console report with clear SAME / only-in-DB-1 / only-in-DB-2 / different summary
- Excel difference report (`.xlsx` via openpyxl)
- `apply`: generate `ALTER TABLE ... ADD CONSTRAINT` DDL; **dry-run by default**; require `--yes` to apply
- `--mock` fixture mode — no live database credentials required

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

Or with pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configuration

Copy the example env file and edit hosts/credentials:

```bash
cp .env.example .env
```

Variables: `DB1_HOST`, `DB1_PORT`, `DB1_NAME`, `DB1_USER`, `DB1_PASSWORD`, `DB1_SCHEMA`, `DB1_LABEL` (and the same for `DB2_*`).

DB1 and DB2 can use **different IPs/hosts**. You can also pass `--db1-host`, `--db1-port`, etc.

## Quick commands (recommended)

From the project folder (loads `.env` automatically):

| What you want | Command |
|---------------|---------|
| Full compare | `dbc` or `.\dbc.cmd` |
| Keys only (PK + FK) | `dbc keys` |
| Primary keys only | `dbc primary_keys` |
| Preview missing keys SQL | `dbc apply` |
| Apply missing keys | `dbc apply --yes` |
| No Excel file | `dbc -n` |
| Mock demo (no DB) | `dbc --mock` |

With uv explicitly:

```bash
uv run dbc
uv run dbc keys
uv run dbc apply
```

Long names still work: `uv run pg-schema-compare compare ...`

## Compare (mock / no credentials)

```bash
dbc --mock
dbc keys --mock
dbc primary_keys --mock
```

Other modes: `full`, `tables`, `columns`, `unique_constraints`, `check_constraints`, `indexes`, `sequences`, `keys`, `primary_keys`, `foreign_keys`.

## Compare (live databases)

```bash
dbc
dbc keys
dbc -x reports/schema_diff.xlsx
```

## Apply missing PK/FK

Copies keys that exist on `--source` / `-s` (default `db1`) but are missing on the other side. **Never drops** existing constraints. Default is dry-run (prints SQL only).

```bash
dbc apply
dbc apply --sql-out missing_keys.sql
dbc apply --yes
```

- `-s db1` → add DB-1 keys that are missing on DB-2
- `-s db2` → add DB-2 keys that are missing on DB-1
- With `--mock --yes`, DDL is recorded by an in-memory executor (still no live DB)

Generated SQL looks like:

```sql
ALTER TABLE "public"."orders" ADD CONSTRAINT "orders_pkey" PRIMARY KEY ("id");
ALTER TABLE "public"."orders" ADD CONSTRAINT "orders_customer_id_fkey"
  FOREIGN KEY ("customer_id") REFERENCES "public"."customers" ("id")
  ON UPDATE NO ACTION ON DELETE CASCADE;
```

## Excel output

By default the tool writes `reports/schema_diff.xlsx` (override with `-x PATH`, or skip with `-n`). Sheets include Summary, each metadata category, and an Apply Plan sheet when using `apply`.

## Tests

```bash
uv run pytest -q
```

## Project layout

```
src/pg_schema_compare/   # CLI, introspect, compare, apply, reports, fixtures
tests/                   # Fixture-based unit tests
dbc.cmd / dbc.ps1        # Short Windows launchers
.env.example             # Connection template
```
