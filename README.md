# PostgreSQL schema compare & sync (PK/FK) CLI

Compare schema metadata between two PostgreSQL databases (or mock fixtures) and optionally **add missing primary keys / foreign keys** to the target database.

## Features

- Connect to two PostgreSQL servers via `.env`, environment variables, or CLI flags
- Compare: tables, columns (type + nullability), primary keys, foreign keys, unique constraints, check constraints, indexes, sequences
- Console report with **SAME / ONLY IN DB-1 / ONLY IN DB-2 / TYPE DIFFERENCE** plus a summary
- Excel difference report (`.xlsx` via openpyxl)
- `apply-missing-keys`: generate `ALTER TABLE ... ADD CONSTRAINT` DDL; **dry-run by default**; require `--execute` to apply
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

You can also pass `--db1-host`, `--db1-port`, `--db1-name`, `--db1-user`, `--db1-password`, `--db1-schema` (and `--db2-*`).

## Compare (mock / no credentials)

Full schema compare using built-in fixtures:

```bash
uv run pg-schema-compare compare --mock --excel schema_diff_report.xlsx
```

Primary keys only:

```bash
uv run pg-schema-compare compare --mock --mode primary_keys
```

Foreign keys only:

```bash
uv run pg-schema-compare compare --mock --mode foreign_keys
```

Other `--mode` values: `full`, `tables`, `columns`, `unique_constraints`, `check_constraints`, `indexes`, `sequences`, `keys`.

## Compare (live databases)

```bash
uv run pg-schema-compare compare --env-file .env --excel reports/schema_diff.xlsx
```

## Apply missing PK/FK

Copies keys that exist on `--source` (default `db1`) but are missing on the other side. **Never drops** existing constraints. Default is dry-run (prints SQL only).

Dry-run (safe default):

```bash
uv run pg-schema-compare apply-missing-keys --mock --source db1 --sql-out missing_keys.sql
```

Execute against the target database (explicit flag required):

```bash
uv run pg-schema-compare apply-missing-keys --env-file .env --source db1 --execute
```

- `--source db1` → add DB-1 keys that are missing on DB-2 (target = DB-2)
- `--source db2` → add DB-2 keys that are missing on DB-1 (target = DB-1)
- With `--mock --execute`, DDL is recorded by an in-memory executor (still no live DB)

Generated SQL looks like:

```sql
ALTER TABLE "public"."orders" ADD CONSTRAINT "orders_pkey" PRIMARY KEY ("id");
ALTER TABLE "public"."orders" ADD CONSTRAINT "orders_customer_id_fkey"
  FOREIGN KEY ("customer_id") REFERENCES "public"."customers" ("id")
  ON UPDATE NO ACTION ON DELETE CASCADE;
```

## Excel output

By default the tool writes `schema_diff_report.xlsx` in the current directory (override with `--excel PATH`, or skip with `--no-excel`). Sheets include Summary, each metadata category, and an Apply Plan sheet when using `apply-missing-keys`.

## Tests

```bash
uv run pytest -q
```

## Project layout

```
src/pg_schema_compare/   # CLI, introspect, compare, apply, reports, fixtures
tests/                   # Fixture-based unit tests
.env.example             # Connection template
```
