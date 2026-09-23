"""Generate and optionally execute ALTER TABLE DDL for missing PK/FK constraints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pg_schema_compare.models import ForeignKeyInfo, PrimaryKeyInfo


class SqlExecutor(Protocol):
    def execute(self, sql: str) -> None: ...

    def commit(self) -> None: ...


@dataclass
class PlannedStatement:
    kind: str  # primary_key | foreign_key
    table: str
    constraint_name: str
    sql: str
    description: str


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def qualify(schema: str, table: str) -> str:
    return f"{quote_ident(schema)}.{quote_ident(table)}"


def pk_add_sql(pk: PrimaryKeyInfo) -> str:
    cols = ", ".join(quote_ident(c) for c in pk.columns)
    table = qualify(pk.table_schema, pk.table_name)
    name = quote_ident(pk.constraint_name)
    return f"ALTER TABLE {table} ADD CONSTRAINT {name} PRIMARY KEY ({cols});"


def fk_add_sql(fk: ForeignKeyInfo) -> str:
    cols = ", ".join(quote_ident(c) for c in fk.columns)
    refs = ", ".join(quote_ident(c) for c in fk.ref_columns)
    table = qualify(fk.table_schema, fk.table_name)
    ref = qualify(fk.ref_schema, fk.ref_table)
    name = quote_ident(fk.constraint_name)
    return (
        f"ALTER TABLE {table} ADD CONSTRAINT {name} "
        f"FOREIGN KEY ({cols}) REFERENCES {ref} ({refs}) "
        f"ON UPDATE {fk.on_update} ON DELETE {fk.on_delete};"
    )


def plan_missing_key_ddl(
    primary_keys: list[PrimaryKeyInfo],
    foreign_keys: list[ForeignKeyInfo],
) -> list[PlannedStatement]:
    """Plan ADD PRIMARY KEY then ADD FOREIGN KEY (PKs first for dependency safety)."""
    planned: list[PlannedStatement] = []
    for pk in primary_keys:
        sql = pk_add_sql(pk)
        planned.append(
            PlannedStatement(
                kind="primary_key",
                table=pk.table_key,
                constraint_name=pk.constraint_name,
                sql=sql,
                description=f"ADD PK {pk.constraint_name} on {pk.table_key} ({', '.join(pk.columns)})",
            )
        )
    for fk in foreign_keys:
        sql = fk_add_sql(fk)
        planned.append(
            PlannedStatement(
                kind="foreign_key",
                table=fk.table_key,
                constraint_name=fk.constraint_name,
                sql=sql,
                description=(
                    f"ADD FK {fk.constraint_name} on {fk.table_key} "
                    f"-> {fk.ref_schema}.{fk.ref_table}"
                ),
            )
        )
    return planned


@dataclass
class ApplyResult:
    dry_run: bool
    planned: list[PlannedStatement]
    executed: list[str]
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def apply_statements(
    planned: list[PlannedStatement],
    executor: SqlExecutor | None,
    *,
    execute: bool = False,
) -> ApplyResult:
    """
    Apply planned DDL.

    dry-run (execute=False) is the default: SQL is generated but not run.
    When execute=True, executor must be provided and statements are run in order.
    Never drops or rewrites existing constraints.
    """
    if not execute:
        return ApplyResult(dry_run=True, planned=planned, executed=[], errors=[])

    if executor is None:
        return ApplyResult(
            dry_run=False,
            planned=planned,
            executed=[],
            errors=["execute requested but no database executor was provided"],
        )

    executed: list[str] = []
    errors: list[str] = []
    for stmt in planned:
        try:
            executor.execute(stmt.sql)
            executed.append(stmt.sql)
        except Exception as exc:  # noqa: BLE001 - surface DB errors to CLI
            errors.append(f"{stmt.description}: {exc}")
            break
    if not errors:
        try:
            executor.commit()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"commit failed: {exc}")
    return ApplyResult(dry_run=False, planned=planned, executed=executed, errors=errors)


class PsycopgExecutor:
    def __init__(self, conn: object) -> None:
        self._conn = conn

    def execute(self, sql: str) -> None:
        self._conn.execute(sql)  # type: ignore[attr-defined]

    def commit(self) -> None:
        self._conn.commit()  # type: ignore[attr-defined]


class RecordingExecutor:
    """Mock executor for tests / --mock apply mode."""

    def __init__(self) -> None:
        self.statements: list[str] = []
        self.committed = False

    def execute(self, sql: str) -> None:
        self.statements.append(sql)

    def commit(self) -> None:
        self.committed = True
