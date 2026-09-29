"""Command-line interface for pg-schema-compare."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pg_schema_compare.apply import (
    PsycopgExecutor,
    RecordingExecutor,
    apply_statements,
    plan_missing_key_ddl,
)
from pg_schema_compare.compare import ONLY_MODES, compare_snapshots, missing_keys_for_apply
from pg_schema_compare.config import load_db_config
from pg_schema_compare.excel_report import write_excel_report
from pg_schema_compare.fixtures import load_fixture_pair
from pg_schema_compare.introspect import connect, fetch_snapshot
from pg_schema_compare.report import format_apply_result, format_console_report

# Short + long command names (normalized in main).
COMMAND_ALIASES = {
    "c": "compare",
    "compare": "compare",
    "a": "apply",
    "apply": "apply",
    "apply-missing-keys": "apply",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dbc",
        description=(
            "Compare PostgreSQL schemas between two databases and optionally "
            "add missing primary/foreign keys.\n\n"
            "Quick start (loads .env automatically):\n"
            "  dbc              full compare\n"
            "  dbc keys         compare primary + foreign keys only\n"
            "  dbc apply        preview missing PK/FK SQL (dry-run)\n"
            "  dbc apply --yes  apply missing PK/FK to the target DB"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # Allow: dbc | dbc keys | dbc apply | dbc c | dbc a
    command_choices = sorted(set(COMMAND_ALIASES) | set(ONLY_MODES.keys()))
    parser.add_argument(
        "command",
        nargs="?",
        default="compare",
        choices=command_choices,
        help="compare/c (default), apply/a, or a mode name like keys/tables",
    )
    parser.add_argument(
        "mode_or_extra",
        nargs="?",
        default=None,
        help="Optional: mode name after compare (e.g. dbc compare keys)",
    )
    parser.add_argument(
        "-m",
        "--mode",
        default="full",
        choices=sorted(ONLY_MODES.keys()),
        help="Comparison scope (default: full). Examples: keys, primary_keys, tables",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use built-in fixture metadata instead of live PostgreSQL connections",
    )
    parser.add_argument(
        "-e",
        "--env-file",
        default=None,
        help="Path to .env file (default: load .env from current folder if present)",
    )
    parser.add_argument(
        "-x",
        "--excel",
        default="reports/schema_diff.xlsx",
        help="Excel output path (default: reports/schema_diff.xlsx)",
    )
    parser.add_argument(
        "-n",
        "--no-excel",
        action="store_true",
        help="Skip Excel report generation",
    )
    parser.add_argument(
        "-s",
        "--source",
        choices=["db1", "db2"],
        default="db1",
        help="For apply: side that owns the keys to copy (default: db1)",
    )
    parser.add_argument(
        "--execute",
        "--yes",
        dest="execute",
        action="store_true",
        help="Actually run ADD CONSTRAINT DDL on the target DB (default is dry-run)",
    )
    parser.add_argument(
        "--sql-out",
        default=None,
        help="Optional path to write generated DDL statements",
    )

    # Connection overrides (optional; otherwise env DB1_* / DB2_*)
    for side in ("1", "2"):
        parser.add_argument(f"--db{side}-host", default=None)
        parser.add_argument(f"--db{side}-port", type=int, default=None)
        parser.add_argument(f"--db{side}-name", default=None)
        parser.add_argument(f"--db{side}-user", default=None)
        parser.add_argument(f"--db{side}-password", default=None)
        parser.add_argument(f"--db{side}-schema", default=None)
        parser.add_argument(f"--db{side}-label", default=None)

    return parser


def _normalize_args(args: argparse.Namespace) -> argparse.Namespace:
    first = args.command
    if first in ONLY_MODES:
        # dbc keys  ->  compare with mode=keys
        args.mode = first
        args.command = "compare"
    else:
        args.command = COMMAND_ALIASES[first]

    extra = args.mode_or_extra
    if extra and args.command == "compare" and extra in ONLY_MODES:
        args.mode = extra
    return args


def _load_snapshots(args: argparse.Namespace):
    if args.mock:
        return load_fixture_pair()

    cfg1 = load_db_config(
        "1",
        host=args.db1_host,
        port=args.db1_port,
        database=args.db1_name,
        user=args.db1_user,
        password=args.db1_password,
        schema=args.db1_schema,
        label=args.db1_label,
        env_file=args.env_file,
    )
    cfg2 = load_db_config(
        "2",
        host=args.db2_host,
        port=args.db2_port,
        database=args.db2_name,
        user=args.db2_user,
        password=args.db2_password,
        schema=args.db2_schema,
        label=args.db2_label,
        env_file=args.env_file,
    )
    return _fetch(cfg1), _fetch(cfg2)


def _fetch(cfg):
    print(f"Connecting to {cfg.display()} ...")
    try:
        return fetch_snapshot(cfg)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Could not connect to {cfg.label} at {cfg.host}:{cfg.port} "
            f"(database '{cfg.database}'): {exc}"
        ) from exc


def cmd_compare(args: argparse.Namespace) -> int:
    snap1, snap2 = _load_snapshots(args)
    result = compare_snapshots(snap1, snap2, mode=args.mode)
    print(format_console_report(result))

    if not args.no_excel:
        path = write_excel_report(result, args.excel)
        print(f"\nExcel report written to: {path.resolve()}")
    return 0


def cmd_apply_missing_keys(args: argparse.Namespace) -> int:
    # Always need PK+FK categories for apply
    snap1, snap2 = _load_snapshots(args)
    result = compare_snapshots(snap1, snap2, mode="keys")
    target_snap = snap2 if args.source == "db1" else snap1
    target_tables = {t.name for t in target_snap.tables}
    pks, fks = missing_keys_for_apply(
        result, source=args.source, target_tables=target_tables
    )
    planned = plan_missing_key_ddl(pks, fks)

    if args.sql_out:
        Path(args.sql_out).write_text(
            "\n".join(s.sql for s in planned) + ("\n" if planned else ""),
            encoding="utf-8",
        )
        print(f"SQL written to: {Path(args.sql_out).resolve()}")

    executor = None
    if args.execute:
        if args.mock:
            executor = RecordingExecutor()
            print("Note: --mock --execute records DDL against an in-memory executor (no live DB).")
        else:
            target_side = "2" if args.source == "db1" else "1"
            cfg = load_db_config(
                target_side,
                host=getattr(args, f"db{target_side}_host"),
                port=getattr(args, f"db{target_side}_port"),
                database=getattr(args, f"db{target_side}_name"),
                user=getattr(args, f"db{target_side}_user"),
                password=getattr(args, f"db{target_side}_password"),
                schema=getattr(args, f"db{target_side}_schema"),
                label=getattr(args, f"db{target_side}_label"),
                env_file=args.env_file,
            )
            conn = connect(cfg)
            executor = PsycopgExecutor(conn)

    apply_result = apply_statements(planned, executor, execute=args.execute)
    print(format_apply_result(apply_result))

    # Also emit compare context + excel with apply plan
    print()
    print(format_console_report(result))
    if not args.no_excel:
        path = write_excel_report(result, args.excel, planned=planned)
        print(f"\nExcel report written to: {path.resolve()}")

    if args.execute and args.mock and isinstance(executor, RecordingExecutor):
        print(f"\nMock executor committed={executor.committed}, statements={len(executor.statements)}")

    if apply_result.errors:
        return 1
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = _normalize_args(parser.parse_args(argv))
    try:
        if args.command == "compare":
            code = cmd_compare(args)
        else:
            code = cmd_apply_missing_keys(args)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    raise SystemExit(code)


if __name__ == "__main__":
    main()
