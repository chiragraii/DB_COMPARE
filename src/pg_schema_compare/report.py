"""Console and shared formatting for comparison / apply reports."""

from __future__ import annotations

from pg_schema_compare.apply import ApplyResult, PlannedStatement
from pg_schema_compare.models import CategoryDiff, CompareResult

STATUS_LABELS = {
    "SAME": "SAME",
    "ONLY_IN_DB1": "ONLY IN DB-1",
    "ONLY_IN_DB2": "ONLY IN DB-2",
    "TYPE_DIFFERENCE": "TYPE DIFFERENCE",
}


def format_console_report(result: CompareResult) -> str:
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("POSTGRESQL SCHEMA COMPARISON REPORT")
    lines.append(f"DB-1: {result.db1_label}")
    lines.append(f"DB-2: {result.db2_label}")
    lines.append("=" * 72)
    lines.append("")
    lines.append("--- SUMMARY ---")
    lines.append(
        f"{'Category':<22} {'SAME':>6} {'ONLY DB-1':>10} {'ONLY DB-2':>10} {'TYPE DIFF':>10}"
    )
    lines.append("-" * 72)
    total_same = total_o1 = total_o2 = total_td = 0
    for name, same, o1, o2, td in result.summary_rows():
        lines.append(f"{name:<22} {same:>6} {o1:>10} {o2:>10} {td:>10}")
        total_same += same
        total_o1 += o1
        total_o2 += o2
        total_td += td
    lines.append("-" * 72)
    lines.append(
        f"{'TOTAL':<22} {total_same:>6} {total_o1:>10} {total_o2:>10} {total_td:>10}"
    )
    lines.append("")

    for name, cat in result.categories.items():
        lines.extend(_format_category(name, cat, result.db1_label, result.db2_label))
    return "\n".join(lines)


def _format_category(
    name: str,
    cat: CategoryDiff,
    db1_label: str,
    db2_label: str,
) -> list[str]:
    lines = [f"=== {name.upper().replace('_', ' ')} ===", ""]
    if not (cat.same or cat.only_db1 or cat.only_db2 or cat.type_diff):
        lines.append("(none)")
        lines.append("")
        return lines

    if cat.same:
        lines.append(f"SAME ({len(cat.same)}):")
        for item in cat.same:
            lines.append(f"  - {item.key}")
        lines.append("")

    if cat.only_db1:
        lines.append(f"ONLY IN DB-1 [{db1_label}] ({len(cat.only_db1)}):")
        for item in cat.only_db1:
            lines.append(f"  - {item.detail_db1 or item.key}")
        lines.append("")

    if cat.only_db2:
        lines.append(f"ONLY IN DB-2 [{db2_label}] ({len(cat.only_db2)}):")
        for item in cat.only_db2:
            lines.append(f"  - {item.detail_db2 or item.key}")
        lines.append("")

    if cat.type_diff:
        lines.append(f"TYPE DIFFERENCE ({len(cat.type_diff)}):")
        for item in cat.type_diff:
            lines.append(f"  - {item.key}")
            lines.append(f"      DB-1: {item.detail_db1}")
            lines.append(f"      DB-2: {item.detail_db2}")
        lines.append("")

    return lines


def format_apply_plan(planned: list[PlannedStatement], *, dry_run: bool) -> str:
    mode = "DRY-RUN (no changes will be applied)" if dry_run else "EXECUTE"
    lines = [
        "=" * 72,
        f"APPLY MISSING KEYS — {mode}",
        "=" * 72,
        "",
    ]
    if not planned:
        lines.append("No missing primary keys or foreign keys to add.")
        return "\n".join(lines)

    lines.append(f"Planned statements: {len(planned)}")
    lines.append("")
    for i, stmt in enumerate(planned, 1):
        lines.append(f"{i}. [{stmt.kind}] {stmt.description}")
        lines.append(f"   SQL: {stmt.sql}")
        lines.append("")
    if dry_run:
        lines.append("Re-run with --execute to apply these statements to the target database.")
    return "\n".join(lines)


def format_apply_result(result: ApplyResult) -> str:
    lines = [format_apply_plan(result.planned, dry_run=result.dry_run), ""]
    if result.dry_run:
        return "\n".join(lines).rstrip()
    lines.append("--- EXECUTION ---")
    lines.append(f"Executed: {len(result.executed)}")
    for sql in result.executed:
        lines.append(f"  OK: {sql}")
    if result.errors:
        lines.append("Errors:")
        for err in result.errors:
            lines.append(f"  ERROR: {err}")
    else:
        lines.append("All statements applied successfully.")
    return "\n".join(lines)
