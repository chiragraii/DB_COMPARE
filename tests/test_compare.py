"""Unit tests using fixture metadata (no live PostgreSQL required)."""

from __future__ import annotations

from pathlib import Path

from pg_schema_compare.apply import (
    RecordingExecutor,
    apply_statements,
    fk_add_sql,
    pk_add_sql,
    plan_missing_key_ddl,
)
from pg_schema_compare.compare import compare_snapshots, missing_keys_for_apply
from pg_schema_compare.excel_report import write_excel_report
from pg_schema_compare.fixtures import fixture_db1, fixture_db2, load_fixture_pair
from pg_schema_compare.report import format_console_report


def test_fixture_pair_loads():
    db1, db2 = load_fixture_pair()
    assert db1.schema_name == "public"
    assert len(db1.tables) == 4
    assert len(db2.tables) == 4


def test_full_compare_summary_categories():
    db1, db2 = load_fixture_pair()
    result = compare_snapshots(db1, db2, mode="full")
    assert set(result.categories) >= {
        "tables",
        "columns",
        "primary_keys",
        "foreign_keys",
        "indexes",
    }
    tables = result.categories["tables"]
    assert any(i.key == "audit_log" for i in tables.only_db1)
    assert any(i.key == "payments" for i in tables.only_db2)
    assert any(i.key == "customers" for i in tables.same)


def test_column_type_difference():
    result = compare_snapshots(fixture_db1(), fixture_db2(), mode="columns")
    diffs = result.categories["columns"].type_diff
    assert any("email" in d.key for d in diffs)


def test_primary_keys_only_mode():
    result = compare_snapshots(fixture_db1(), fixture_db2(), mode="primary_keys")
    assert list(result.categories.keys()) == ["primary_keys"]
    only1 = result.categories["primary_keys"].only_db1
    assert any(i.key == "orders" for i in only1)


def test_foreign_keys_only_mode():
    result = compare_snapshots(fixture_db1(), fixture_db2(), mode="foreign_keys")
    only1 = result.categories["foreign_keys"].only_db1
    assert any("orders" in i.key and "customer_id" in i.key for i in only1)


def test_missing_keys_for_apply_db1_to_db2():
    db1, db2 = fixture_db1(), fixture_db2()
    result = compare_snapshots(db1, db2, mode="keys")
    target_tables = {t.name for t in db2.tables}
    pks, fks = missing_keys_for_apply(
        result, source="db1", target_tables=target_tables
    )
    assert any(pk.table_name == "orders" for pk in pks)
    assert all(pk.table_name != "audit_log" for pk in pks)
    assert any(fk.constraint_name == "orders_customer_id_fkey" for fk in fks)


def test_pk_fk_sql_generation():
    db1 = fixture_db1()
    pk = next(p for p in db1.primary_keys if p.table_name == "orders")
    fk = next(f for f in db1.foreign_keys if f.constraint_name == "orders_customer_id_fkey")
    pk_sql = pk_add_sql(pk)
    fk_sql = fk_add_sql(fk)
    assert 'ADD CONSTRAINT "orders_pkey" PRIMARY KEY ("id")' in pk_sql
    assert "FOREIGN KEY" in fk_sql
    assert 'REFERENCES "public"."customers"' in fk_sql
    assert "ON DELETE CASCADE" in fk_sql


def test_apply_dry_run_default():
    db1, db2 = fixture_db1(), fixture_db2()
    result = compare_snapshots(db1, db2, mode="keys")
    pks, fks = missing_keys_for_apply(
        result, source="db1", target_tables={t.name for t in db2.tables}
    )
    planned = plan_missing_key_ddl(pks, fks)
    assert planned
    assert all("audit_log" not in p.table for p in planned)
    # PKs before FKs
    assert planned[0].kind == "primary_key"
    apply_result = apply_statements(planned, None, execute=False)
    assert apply_result.dry_run is True
    assert apply_result.executed == []


def test_apply_execute_with_recording_executor():
    db1, db2 = fixture_db1(), fixture_db2()
    result = compare_snapshots(db1, db2, mode="keys")
    pks, fks = missing_keys_for_apply(
        result, source="db1", target_tables={t.name for t in db2.tables}
    )
    planned = plan_missing_key_ddl(pks, fks)
    executor = RecordingExecutor()
    apply_result = apply_statements(planned, executor, execute=True)
    assert apply_result.ok
    assert len(executor.statements) == len(planned)
    assert executor.committed is True


def test_console_report_contains_sections():
    result = compare_snapshots(fixture_db1(), fixture_db2(), mode="full")
    text = format_console_report(result)
    assert "Schema comparison report" in text
    assert "Summary" in text
    assert "Only in DB-1" in text
    assert "Only in DB-2" in text
    assert "Different definition" in text or "Different" in text
    assert "How to read this report" in text


def test_cli_short_aliases_and_mode_shortcut():
    from pg_schema_compare.cli import build_parser, _normalize_args

    args = _normalize_args(build_parser().parse_args(["keys", "-n", "--mock"]))
    assert args.command == "compare"
    assert args.mode == "keys"
    assert args.no_excel is True

    args = _normalize_args(build_parser().parse_args(["a", "-s", "db2"]))
    assert args.command == "apply"
    assert args.source == "db2"

    args = _normalize_args(build_parser().parse_args(["apply-missing-keys", "--yes"]))
    assert args.command == "apply"
    assert args.execute is True


def test_excel_report(tmp_path: Path):
    db1, db2 = fixture_db1(), fixture_db2()
    result = compare_snapshots(db1, db2, mode="full")
    pks, fks = missing_keys_for_apply(
        compare_snapshots(db1, db2, mode="keys"),
        source="db1",
        target_tables={t.name for t in db2.tables},
    )
    planned = plan_missing_key_ddl(pks, fks)
    out = tmp_path / "diff.xlsx"
    path = write_excel_report(result, out, planned=planned)
    assert path.exists()
    assert path.stat().st_size > 0
