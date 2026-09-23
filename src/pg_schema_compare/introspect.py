"""Introspect PostgreSQL schema metadata via information_schema / pg_catalog."""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from pg_schema_compare.config import DbConfig
from pg_schema_compare.models import (
    CheckConstraintInfo,
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    PrimaryKeyInfo,
    SchemaSnapshot,
    SequenceInfo,
    TableRef,
    UniqueConstraintInfo,
)


def connect(config: DbConfig) -> psycopg.Connection:
    return psycopg.connect(config.dsn(), row_factory=dict_row)


def fetch_snapshot(config: DbConfig) -> SchemaSnapshot:
    with connect(config) as conn:
        return fetch_snapshot_from_conn(conn, config.label, config.schema)


def fetch_snapshot_from_conn(
    conn: psycopg.Connection,
    label: str,
    schema_name: str,
) -> SchemaSnapshot:
    tables = _fetch_tables(conn, schema_name)
    columns = _fetch_columns(conn, schema_name)
    primary_keys = _fetch_primary_keys(conn, schema_name)
    foreign_keys = _fetch_foreign_keys(conn, schema_name)
    unique_constraints = _fetch_unique_constraints(conn, schema_name)
    check_constraints = _fetch_check_constraints(conn, schema_name)
    indexes = _fetch_indexes(conn, schema_name)
    sequences = _fetch_sequences(conn, schema_name)
    return SchemaSnapshot(
        label=label,
        schema_name=schema_name,
        tables=tables,
        columns=columns,
        primary_keys=primary_keys,
        foreign_keys=foreign_keys,
        unique_constraints=unique_constraints,
        check_constraints=check_constraints,
        indexes=indexes,
        sequences=sequences,
    )


def _fetch_tables(conn: psycopg.Connection, schema: str) -> list[TableRef]:
    rows = conn.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema = %s
          AND table_type = 'BASE TABLE'
        ORDER BY table_schema, table_name
        """,
        (schema,),
    ).fetchall()
    return [TableRef(schema=r["table_schema"], name=r["table_name"]) for r in rows]


def _fetch_columns(conn: psycopg.Connection, schema: str) -> list[ColumnInfo]:
    rows = conn.execute(
        """
        SELECT
            table_schema,
            table_name,
            column_name,
            data_type,
            udt_name,
            is_nullable,
            character_maximum_length,
            numeric_precision,
            numeric_scale,
            column_default,
            ordinal_position
        FROM information_schema.columns
        WHERE table_schema = %s
        ORDER BY table_schema, table_name, ordinal_position
        """,
        (schema,),
    ).fetchall()
    return [
        ColumnInfo(
            table_schema=r["table_schema"],
            table_name=r["table_name"],
            column_name=r["column_name"],
            data_type=r["data_type"],
            udt_name=r["udt_name"],
            is_nullable=r["is_nullable"] == "YES",
            character_maximum_length=r["character_maximum_length"],
            numeric_precision=r["numeric_precision"],
            numeric_scale=r["numeric_scale"],
            column_default=r["column_default"],
            ordinal_position=r["ordinal_position"],
        )
        for r in rows
    ]


def _constraint_columns(
    conn: psycopg.Connection,
    schema: str,
    constraint_type: str,
) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            tc.constraint_name,
            tc.table_schema,
            tc.table_name,
            kcu.column_name,
            kcu.ordinal_position
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
         AND tc.table_name = kcu.table_name
        WHERE tc.table_schema = %s
          AND tc.constraint_type = %s
        ORDER BY tc.constraint_name, kcu.ordinal_position
        """,
        (schema, constraint_type),
    ).fetchall()
    grouped: dict[str, dict[str, Any]] = {}
    for r in rows:
        key = f"{r['table_schema']}.{r['table_name']}.{r['constraint_name']}"
        if key not in grouped:
            grouped[key] = {
                "constraint_name": r["constraint_name"],
                "table_schema": r["table_schema"],
                "table_name": r["table_name"],
                "columns": [],
            }
        grouped[key]["columns"].append(r["column_name"])
    return grouped


def _fetch_primary_keys(conn: psycopg.Connection, schema: str) -> list[PrimaryKeyInfo]:
    grouped = _constraint_columns(conn, schema, "PRIMARY KEY")
    return [
        PrimaryKeyInfo(
            constraint_name=g["constraint_name"],
            table_schema=g["table_schema"],
            table_name=g["table_name"],
            columns=tuple(g["columns"]),
        )
        for g in grouped.values()
    ]


def _fetch_unique_constraints(conn: psycopg.Connection, schema: str) -> list[UniqueConstraintInfo]:
    grouped = _constraint_columns(conn, schema, "UNIQUE")
    return [
        UniqueConstraintInfo(
            constraint_name=g["constraint_name"],
            table_schema=g["table_schema"],
            table_name=g["table_name"],
            columns=tuple(g["columns"]),
        )
        for g in grouped.values()
    ]


def _fetch_foreign_keys(conn: psycopg.Connection, schema: str) -> list[ForeignKeyInfo]:
    rows = conn.execute(
        """
        SELECT
            tc.constraint_name,
            tc.table_schema,
            tc.table_name,
            kcu.column_name,
            kcu.ordinal_position,
            ccu.table_schema AS ref_schema,
            ccu.table_name AS ref_table,
            ccu.column_name AS ref_column,
            rc.update_rule,
            rc.delete_rule,
            rc.match_option
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
         AND tc.table_name = kcu.table_name
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
         AND tc.table_schema = ccu.constraint_schema
        JOIN information_schema.referential_constraints rc
          ON tc.constraint_name = rc.constraint_name
         AND tc.table_schema = rc.constraint_schema
        WHERE tc.table_schema = %s
          AND tc.constraint_type = 'FOREIGN KEY'
        ORDER BY tc.constraint_name, kcu.ordinal_position
        """,
        (schema,),
    ).fetchall()

    grouped: dict[str, dict[str, Any]] = {}
    for r in rows:
        key = f"{r['table_schema']}.{r['table_name']}.{r['constraint_name']}"
        if key not in grouped:
            grouped[key] = {
                "constraint_name": r["constraint_name"],
                "table_schema": r["table_schema"],
                "table_name": r["table_name"],
                "columns": [],
                "ref_schema": r["ref_schema"],
                "ref_table": r["ref_table"],
                "ref_columns": [],
                "on_update": r["update_rule"],
                "on_delete": r["delete_rule"],
                "match_option": r["match_option"],
            }
        # key_column_usage and constraint_column_usage may duplicate; keep order
        if r["column_name"] not in grouped[key]["columns"]:
            grouped[key]["columns"].append(r["column_name"])
        if r["ref_column"] not in grouped[key]["ref_columns"]:
            grouped[key]["ref_columns"].append(r["ref_column"])

    return [
        ForeignKeyInfo(
            constraint_name=g["constraint_name"],
            table_schema=g["table_schema"],
            table_name=g["table_name"],
            columns=tuple(g["columns"]),
            ref_schema=g["ref_schema"],
            ref_table=g["ref_table"],
            ref_columns=tuple(g["ref_columns"]),
            on_update=g["on_update"],
            on_delete=g["on_delete"],
            match_option=g["match_option"],
        )
        for g in grouped.values()
    ]


def _fetch_check_constraints(conn: psycopg.Connection, schema: str) -> list[CheckConstraintInfo]:
    rows = conn.execute(
        """
        SELECT
            tc.constraint_name,
            tc.table_schema,
            tc.table_name,
            cc.check_clause
        FROM information_schema.table_constraints tc
        JOIN information_schema.check_constraints cc
          ON tc.constraint_name = cc.constraint_name
         AND tc.constraint_schema = cc.constraint_schema
        WHERE tc.table_schema = %s
          AND tc.constraint_type = 'CHECK'
          AND tc.constraint_name NOT LIKE '%%_not_null'
        ORDER BY tc.table_name, tc.constraint_name
        """,
        (schema,),
    ).fetchall()
    return [
        CheckConstraintInfo(
            constraint_name=r["constraint_name"],
            table_schema=r["table_schema"],
            table_name=r["table_name"],
            check_clause=r["check_clause"],
        )
        for r in rows
    ]


def _fetch_indexes(conn: psycopg.Connection, schema: str) -> list[IndexInfo]:
    rows = conn.execute(
        """
        SELECT
            n.nspname AS schema_name,
            t.relname AS table_name,
            i.relname AS index_name,
            ix.indisunique AS is_unique,
            ix.indisprimary AS is_primary,
            pg_get_indexdef(ix.indexrelid) AS index_definition,
            array_agg(a.attname ORDER BY x.n) AS columns
        FROM pg_index ix
        JOIN pg_class t ON t.oid = ix.indrelid
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS x(attnum, n) ON true
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = x.attnum
        WHERE n.nspname = %s
          AND NOT ix.indisprimary
        GROUP BY n.nspname, t.relname, i.relname, ix.indisunique, ix.indisprimary, ix.indexrelid
        ORDER BY n.nspname, t.relname, i.relname
        """,
        (schema,),
    ).fetchall()
    result: list[IndexInfo] = []
    for r in rows:
        cols = r["columns"]
        if isinstance(cols, list):
            col_tuple = tuple(cols)
        else:
            # psycopg may return list-like
            col_tuple = tuple(cols) if cols else ()
        result.append(
            IndexInfo(
                schema_name=r["schema_name"],
                table_name=r["table_name"],
                index_name=r["index_name"],
                columns=col_tuple,
                is_unique=bool(r["is_unique"]),
                is_primary=bool(r["is_primary"]),
                index_definition=r["index_definition"] or "",
            )
        )
    return result


def _fetch_sequences(conn: psycopg.Connection, schema: str) -> list[SequenceInfo]:
    rows = conn.execute(
        """
        SELECT
            sequence_schema,
            sequence_name,
            data_type,
            start_value,
            minimum_value,
            maximum_value,
            increment
        FROM information_schema.sequences
        WHERE sequence_schema = %s
        ORDER BY sequence_schema, sequence_name
        """,
        (schema,),
    ).fetchall()
    return [
        SequenceInfo(
            sequence_schema=r["sequence_schema"],
            sequence_name=r["sequence_name"],
            data_type=r["data_type"],
            start_value=str(r["start_value"]) if r["start_value"] is not None else None,
            minimum_value=str(r["minimum_value"]) if r["minimum_value"] is not None else None,
            maximum_value=str(r["maximum_value"]) if r["maximum_value"] is not None else None,
            increment=str(r["increment"]) if r["increment"] is not None else None,
        )
        for r in rows
    ]
