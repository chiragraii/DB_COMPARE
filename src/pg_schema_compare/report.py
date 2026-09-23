"""Console and shared formatting for comparison / apply reports."""

from __future__ import annotations

from typing import Any

from pg_schema_compare.apply import ApplyResult, PlannedStatement
from pg_schema_compare.models import (
    CategoryDiff,
    CheckConstraintInfo,
    ColumnInfo,
    CompareResult,
    DiffItem,
    ForeignKeyInfo,
    IndexInfo,
    PrimaryKeyInfo,
    SequenceInfo,
    UniqueConstraintInfo,
)

CATEGORY_TITLES = {
    "tables": "Tables",
    "columns": "Columns",
    "primary_keys": "Primary keys",
    "foreign_keys": "Foreign keys",
    "unique_constraints": "Unique constraints",
    "check_constraints": "Check constraints",
    "indexes": "Indexes",
    "sequences": "Sequences",
}

STATUS_LABELS = {
    "SAME": "Same in both",
    "ONLY_IN_DB1": "Only in DB-1",
    "ONLY_IN_DB2": "Only in DB-2",
    "TYPE_DIFFERENCE": "Different definition",
}


def format_console_report(result: CompareResult) -> str:
    db1 = result.db1_label
    db2 = result.db2_label
    total_same = total_o1 = total_o2 = total_td = 0
    for _, same, o1, o2, td in result.summary_rows():
        total_same += same
        total_o1 += o1
        total_o2 += o2
        total_td += td
    total_diff = total_o1 + total_o2 + total_td

    lines: list[str] = []
    lines.append("")
    lines.append("=" * 72)
    lines.append("  Schema comparison report")
    lines.append("=" * 72)
    lines.append(f"  DB-1 (left):  {db1}")
    lines.append(f"  DB-2 (right): {db2}")
    lines.append("")
    if total_diff == 0:
        lines.append("  Result: Schemas match for the categories compared.")
    else:
        lines.append(
            f"  Result: {total_diff} difference(s) found "
            f"({total_o1} only in DB-1, {total_o2} only in DB-2, "
            f"{total_td} definition mismatch(es))."
        )
    lines.append("")
    lines.append("  How to read this report")
    lines.append("  -----------------------")
    lines.append(f"  - Same in both     = exists in both {db1} and {db2}")
    lines.append(f"  - Only in DB-1     = in {db1}, missing from {db2}")
    lines.append(f"  - Only in DB-2     = in {db2}, missing from {db1}")
    lines.append("  - Different        = same object name, different definition")
    lines.append("")
    lines.append("-" * 72)
    lines.append("  Summary")
    lines.append("-" * 72)
    lines.append(
        f"  {'Category':<22} {'Same':>6} {'Only DB-1':>10} "
        f"{'Only DB-2':>10} {'Different':>10}"
    )
    lines.append("  " + "-" * 68)
    for name, same, o1, o2, td in result.summary_rows():
        title = CATEGORY_TITLES.get(name, name.replace("_", " ").title())
        mark = " *" if (o1 or o2 or td) else ""
        lines.append(
            f"  {title:<22} {same:>6} {o1:>10} {o2:>10} {td:>10}{mark}"
        )
    lines.append("  " + "-" * 68)
    lines.append(
        f"  {'TOTAL':<22} {total_same:>6} {total_o1:>10} "
        f"{total_o2:>10} {total_td:>10}"
    )
    if total_diff:
        lines.append("")
        lines.append("  (* = category has differences; details below)")
    lines.append("")

    for name, cat in result.categories.items():
        lines.extend(_format_category(name, cat, db1, db2))

    lines.append("=" * 72)
    return "\n".join(lines)


def _format_category(
    name: str,
    cat: CategoryDiff,
    db1_label: str,
    db2_label: str,
) -> list[str]:
    title = CATEGORY_TITLES.get(name, name.replace("_", " ").title())
    lines = [f"  {title}", "  " + ("-" * len(title))]

    if not (cat.same or cat.only_db1 or cat.only_db2 or cat.type_diff):
        lines.append("  (nothing in this category)")
        lines.append("")
        return lines

    if cat.difference_count == 0 and cat.same:
        lines.append(f"  All {len(cat.same)} item(s) match in both databases.")
        lines.append("")
        # Still list matches briefly when few; otherwise keep summary-only for SAME
        if len(cat.same) <= 12:
            for item in cat.same:
                lines.append(f"    OK  {_describe_item(item, prefer='db1')}")
            lines.append("")
        return lines

    if cat.only_db1:
        lines.append("")
        lines.append(
            f"  Only in DB-1 [{db1_label}] - missing from DB-2 ({len(cat.only_db1)})"
        )
        for item in cat.only_db1:
            lines.append(f"    - {_describe_item(item, prefer='db1')}")

    if cat.only_db2:
        lines.append("")
        lines.append(
            f"  Only in DB-2 [{db2_label}] - missing from DB-1 ({len(cat.only_db2)})"
        )
        for item in cat.only_db2:
            lines.append(f"    - {_describe_item(item, prefer='db2')}")

    if cat.type_diff:
        lines.append("")
        lines.append(f"  Different definition ({len(cat.type_diff)})")
        for item in cat.type_diff:
            lines.append(f"    - {_short_key(item)}")
            lines.append(f"        DB-1: {item.detail_db1 or _describe_item(item, prefer='db1')}")
            lines.append(f"        DB-2: {item.detail_db2 or _describe_item(item, prefer='db2')}")

    if cat.same and cat.difference_count:
        lines.append("")
        lines.append(f"  Same in both ({len(cat.same)}) - hidden; see summary counts")

    lines.append("")
    return lines


def _short_key(item: DiffItem) -> str:
    obj = item.object_db1 or item.object_db2
    if obj is not None:
        return _object_headline(obj)
    # Fall back: strip internal :: markers from match keys
    key = item.key.replace("::", " / ")
    return key


def _describe_item(item: DiffItem, *, prefer: str) -> str:
    obj = item.object_db1 if prefer == "db1" else item.object_db2
    if obj is None:
        obj = item.object_db1 or item.object_db2
    if obj is not None:
        return _object_friendly(obj)
    detail = item.detail_db1 if prefer == "db1" else item.detail_db2
    if detail:
        return detail
    return _short_key(item)


def _object_headline(obj: Any) -> str:
    if isinstance(obj, ColumnInfo):
        return f"{obj.table_key}.{obj.column_name}"
    if isinstance(obj, (PrimaryKeyInfo, ForeignKeyInfo, UniqueConstraintInfo, CheckConstraintInfo)):
        return f"{obj.table_key}  ({obj.constraint_name})"
    if isinstance(obj, IndexInfo):
        return f"{obj.schema_name}.{obj.table_name}  ({obj.index_name})"
    if isinstance(obj, SequenceInfo):
        return f"{obj.sequence_schema}.{obj.sequence_name}"
    if hasattr(obj, "qualified"):
        return str(obj.qualified)
    if hasattr(obj, "name"):
        return str(obj.name)
    return str(obj)


def _object_friendly(obj: Any) -> str:
    if isinstance(obj, ColumnInfo):
        return f"Column {obj.table_key}.{obj.column_name} - {obj.type_signature}"
    if isinstance(obj, PrimaryKeyInfo):
        cols = ", ".join(obj.columns)
        return (
            f"Table {obj.table_key} - primary key \"{obj.constraint_name}\" "
            f"on ({cols})"
        )
    if isinstance(obj, ForeignKeyInfo):
        cols = ", ".join(obj.columns)
        refs = ", ".join(obj.ref_columns)
        return (
            f"Table {obj.table_key} - foreign key \"{obj.constraint_name}\": "
            f"({cols}) -> {obj.ref_schema}.{obj.ref_table} ({refs}) "
            f"[ON UPDATE {obj.on_update}, ON DELETE {obj.on_delete}]"
        )
    if isinstance(obj, UniqueConstraintInfo):
        cols = ", ".join(obj.columns)
        return (
            f"Table {obj.table_key} - unique \"{obj.constraint_name}\" "
            f"on ({cols})"
        )
    if isinstance(obj, CheckConstraintInfo):
        return (
            f"Table {obj.table_key} - check \"{obj.constraint_name}\": "
            f"{obj.check_clause}"
        )
    if isinstance(obj, IndexInfo):
        cols = ", ".join(obj.columns) if obj.columns else "?"
        uniq = "unique " if obj.is_unique else ""
        return (
            f"Table {obj.schema_name}.{obj.table_name} - {uniq}index "
            f"\"{obj.index_name}\" on ({cols})"
        )
    if isinstance(obj, SequenceInfo):
        return f"Sequence {obj.sequence_schema}.{obj.sequence_name}"
    if hasattr(obj, "qualified"):
        return f"Table {obj.qualified}"
    if hasattr(obj, "name"):
        return f"Table {obj.name}"
    return str(obj)


def format_apply_plan(planned: list[PlannedStatement], *, dry_run: bool) -> str:
    mode = "preview only - nothing was changed" if dry_run else "APPLYING CHANGES"
    lines = [
        "",
        "=" * 72,
        f"  Add missing keys — {mode}",
        "=" * 72,
        "",
    ]
    if not planned:
        lines.append("  No missing primary keys or foreign keys to add.")
        lines.append("")
        return "\n".join(lines)

    lines.append(f"  Planned changes: {len(planned)}")
    lines.append("")
    for i, stmt in enumerate(planned, 1):
        kind = "Primary key" if stmt.kind == "primary_key" else "Foreign key"
        lines.append(f"  {i}. {kind}: {stmt.description}")
        lines.append(f"     SQL: {stmt.sql}")
        lines.append("")
    if dry_run:
        lines.append(
            "  This was a dry run. Re-run with --execute to apply these "
            "statements to the target database."
        )
        lines.append("")
    return "\n".join(lines)


def format_apply_result(result: ApplyResult) -> str:
    lines = [format_apply_plan(result.planned, dry_run=result.dry_run)]
    if result.dry_run:
        return "\n".join(lines).rstrip() + "\n"
    lines.append("  Execution result")
    lines.append("  ----------------")
    lines.append(f"  Executed successfully: {len(result.executed)}")
    for sql in result.executed:
        lines.append(f"    OK  {sql}")
    if result.errors:
        lines.append("  Errors:")
        for err in result.errors:
            lines.append(f"    ERROR  {err}")
    else:
        lines.append("  All statements applied successfully.")
    lines.append("")
    return "\n".join(lines)
