"""Compare two SchemaSnapshot objects across metadata categories."""

from __future__ import annotations

from typing import Any

from pg_schema_compare.models import (
    CategoryDiff,
    CompareResult,
    DiffItem,
    SchemaSnapshot,
)

CATEGORIES = (
    "tables",
    "columns",
    "primary_keys",
    "foreign_keys",
    "unique_constraints",
    "check_constraints",
    "indexes",
    "sequences",
)

ONLY_MODES = {
    "full": CATEGORIES,
    "tables": ("tables",),
    "columns": ("columns",),
    "primary_keys": ("primary_keys",),
    "foreign_keys": ("foreign_keys",),
    "unique_constraints": ("unique_constraints",),
    "check_constraints": ("check_constraints",),
    "indexes": ("indexes",),
    "sequences": ("sequences",),
    "keys": ("primary_keys", "foreign_keys"),
}


def compare_snapshots(
    db1: SchemaSnapshot,
    db2: SchemaSnapshot,
    *,
    mode: str = "full",
) -> CompareResult:
    categories = ONLY_MODES.get(mode)
    if categories is None:
        raise ValueError(f"Unknown compare mode: {mode}. Choose from {sorted(ONLY_MODES)}")

    result = CompareResult(db1_label=db1.label, db2_label=db2.label)
    for category in categories:
        result.categories[category] = _compare_category(category, db1, db2)
    return result


def _items_for(category: str, snap: SchemaSnapshot) -> list[Any]:
    return list(getattr(snap, category))


def _identity(category: str, obj: Any) -> str:
    if category == "tables":
        return obj.qualified
    if hasattr(obj, "identity_key"):
        return obj.identity_key()
    return str(obj)


def _detail(category: str, obj: Any) -> str:
    if category == "tables":
        return obj.qualified
    if category == "columns":
        return f"{obj.identity_key()} :: {obj.type_signature}"
    if hasattr(obj, "signature"):
        base = obj.identity_key() if hasattr(obj, "identity_key") else str(obj)
        return f"{base} :: {obj.signature()}"
    return str(obj)


def _match_key(category: str, obj: Any) -> str:
    """Key used to pair objects across DBs for type-difference detection."""
    if category == "tables":
        return obj.name
    if category == "columns":
        return f"{obj.table_name}.{obj.column_name}"
    if category == "primary_keys":
        # Pair by table — one PK per table typically
        return obj.table_name
    if category == "foreign_keys":
        # Prefer constraint name; also allow column-set match
        return f"{obj.table_name}.{obj.constraint_name}"
    if category == "unique_constraints":
        return f"{obj.table_name}.{obj.constraint_name}"
    if category == "check_constraints":
        return f"{obj.table_name}.{obj.constraint_name}"
    if category == "indexes":
        return f"{obj.table_name}.{obj.index_name}"
    if category == "sequences":
        return obj.sequence_name
    return _identity(category, obj)


def _is_equivalent(category: str, a: Any, b: Any) -> bool:
    if category == "tables":
        return a.name == b.name
    if category == "columns":
        return (
            a.column_name == b.column_name
            and a.table_name == b.table_name
            and a.type_signature == b.type_signature
        )
    if category == "primary_keys":
        return a.columns == b.columns
    if category == "foreign_keys":
        return (
            a.columns == b.columns
            and a.ref_table == b.ref_table
            and a.ref_columns == b.ref_columns
            and a.on_update == b.on_update
            and a.on_delete == b.on_delete
        )
    if category == "unique_constraints":
        return a.columns == b.columns
    if category == "check_constraints":
        return _normalize_check(a.check_clause) == _normalize_check(b.check_clause)
    if category == "indexes":
        return a.columns == b.columns and a.is_unique == b.is_unique
    if category == "sequences":
        return a.signature() == b.signature()
    return _identity(category, a) == _identity(category, b)


def _normalize_check(clause: str) -> str:
    return " ".join(clause.lower().split())


def _compare_category(
    category: str,
    db1: SchemaSnapshot,
    db2: SchemaSnapshot,
) -> CategoryDiff:
    items1 = _items_for(category, db1)
    items2 = _items_for(category, db2)

    map1: dict[str, Any] = {}
    map2: dict[str, Any] = {}
    for obj in items1:
        map1[_match_key(category, obj)] = obj
    for obj in items2:
        map2[_match_key(category, obj)] = obj

    # For foreign keys / unique / indexes also try semantic pairing when names differ
    if category in {"foreign_keys", "unique_constraints"}:
        map1, map2 = _semantic_pair_maps(category, items1, items2)

    diff = CategoryDiff(category=category)
    all_keys = sorted(set(map1) | set(map2))

    for key in all_keys:
        o1 = map1.get(key)
        o2 = map2.get(key)
        if o1 is not None and o2 is not None:
            if _is_equivalent(category, o1, o2):
                diff.same.append(
                    DiffItem(
                        category=category,
                        status="SAME",
                        key=key,
                        detail_db1=_detail(category, o1),
                        detail_db2=_detail(category, o2),
                        object_db1=o1,
                        object_db2=o2,
                    )
                )
            else:
                diff.type_diff.append(
                    DiffItem(
                        category=category,
                        status="TYPE_DIFFERENCE",
                        key=key,
                        detail_db1=_detail(category, o1),
                        detail_db2=_detail(category, o2),
                        object_db1=o1,
                        object_db2=o2,
                    )
                )
        elif o1 is not None:
            diff.only_db1.append(
                DiffItem(
                    category=category,
                    status="ONLY_IN_DB1",
                    key=key,
                    detail_db1=_detail(category, o1),
                    object_db1=o1,
                )
            )
        else:
            assert o2 is not None
            diff.only_db2.append(
                DiffItem(
                    category=category,
                    status="ONLY_IN_DB2",
                    key=key,
                    detail_db2=_detail(category, o2),
                    object_db2=o2,
                )
            )
    return diff


def _semantic_pair_maps(
    category: str,
    items1: list[Any],
    items2: list[Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Pair constraints by table+columns when names diverge."""

    def semantic_key(obj: Any) -> str:
        if category == "foreign_keys":
            return (
                f"{obj.table_name}|cols={','.join(obj.columns)}|"
                f"ref={obj.ref_table}:{','.join(obj.ref_columns)}"
            )
        return f"{obj.table_name}|cols={','.join(obj.columns)}"

    map1 = {semantic_key(o): o for o in items1}
    map2 = {semantic_key(o): o for o in items2}
    return map1, map2


def missing_keys_for_apply(
    result: CompareResult,
    *,
    source: str = "db1",
    target_tables: set[str] | None = None,
) -> tuple[list[Any], list[Any]]:
    """
    Return PK and FK objects present on source and missing on target.

    source='db1' means add DB1 keys that are missing in DB2 (ONLY_IN_DB1).
    source='db2' means add DB2 keys that are missing in DB1 (ONLY_IN_DB2).

    Only constraints whose table exists on the target are returned (corresponding
    table required). Pass target_tables as unqualified table names, or None to
    skip that filter.
    """
    pk_cat = result.categories.get("primary_keys")
    fk_cat = result.categories.get("foreign_keys")
    if source == "db1":
        pks = [i.object_db1 for i in (pk_cat.only_db1 if pk_cat else []) if i.object_db1]
        fks = [i.object_db1 for i in (fk_cat.only_db1 if fk_cat else []) if i.object_db1]
    elif source == "db2":
        pks = [i.object_db2 for i in (pk_cat.only_db2 if pk_cat else []) if i.object_db2]
        fks = [i.object_db2 for i in (fk_cat.only_db2 if fk_cat else []) if i.object_db2]
    else:
        raise ValueError("source must be 'db1' or 'db2'")

    if target_tables is not None:
        pks = [pk for pk in pks if pk.table_name in target_tables]
        fks = [fk for fk in fks if fk.table_name in target_tables]
    return pks, fks
