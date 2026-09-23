"""Schema metadata models used for comparison and apply."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, order=True)
class TableRef:
    schema: str
    name: str

    @property
    def qualified(self) -> str:
        return f"{self.schema}.{self.name}"

    def __str__(self) -> str:
        return self.qualified


@dataclass(frozen=True, order=True)
class ColumnInfo:
    table_schema: str
    table_name: str
    column_name: str
    data_type: str
    udt_name: str
    is_nullable: bool
    character_maximum_length: int | None = None
    numeric_precision: int | None = None
    numeric_scale: int | None = None
    column_default: str | None = None
    ordinal_position: int = 0

    @property
    def table_key(self) -> str:
        return f"{self.table_schema}.{self.table_name}"

    @property
    def type_signature(self) -> str:
        base = self.data_type
        if self.character_maximum_length is not None and self.data_type in {
            "character varying",
            "character",
            "varchar",
            "char",
        }:
            base = f"{self.data_type}({self.character_maximum_length})"
        elif self.numeric_precision is not None and self.data_type in {
            "numeric",
            "decimal",
        }:
            if self.numeric_scale is not None:
                base = f"{self.data_type}({self.numeric_precision},{self.numeric_scale})"
            else:
                base = f"{self.data_type}({self.numeric_precision})"
        null = "NULL" if self.is_nullable else "NOT NULL"
        return f"{base} {null}"

    def identity_key(self) -> str:
        return f"{self.table_key}.{self.column_name}"


@dataclass(frozen=True, order=True)
class PrimaryKeyInfo:
    constraint_name: str
    table_schema: str
    table_name: str
    columns: tuple[str, ...]

    @property
    def table_key(self) -> str:
        return f"{self.table_schema}.{self.table_name}"

    def identity_key(self) -> str:
        cols = ",".join(self.columns)
        return f"{self.table_key}::pk::{self.constraint_name}::{cols}"

    def signature(self) -> str:
        return f"PRIMARY KEY ({', '.join(self.columns)})"


@dataclass(frozen=True, order=True)
class ForeignKeyInfo:
    constraint_name: str
    table_schema: str
    table_name: str
    columns: tuple[str, ...]
    ref_schema: str
    ref_table: str
    ref_columns: tuple[str, ...]
    on_update: str = "NO ACTION"
    on_delete: str = "NO ACTION"
    match_option: str = "NONE"

    @property
    def table_key(self) -> str:
        return f"{self.table_schema}.{self.table_name}"

    def identity_key(self) -> str:
        cols = ",".join(self.columns)
        refs = ",".join(self.ref_columns)
        return (
            f"{self.table_key}::fk::{self.constraint_name}::"
            f"({cols})->({self.ref_schema}.{self.ref_table}:{refs})"
        )

    def signature(self) -> str:
        cols = ", ".join(self.columns)
        refs = ", ".join(self.ref_columns)
        return (
            f"FOREIGN KEY ({cols}) REFERENCES "
            f"{self.ref_schema}.{self.ref_table} ({refs}) "
            f"ON UPDATE {self.on_update} ON DELETE {self.on_delete}"
        )


@dataclass(frozen=True, order=True)
class UniqueConstraintInfo:
    constraint_name: str
    table_schema: str
    table_name: str
    columns: tuple[str, ...]

    @property
    def table_key(self) -> str:
        return f"{self.table_schema}.{self.table_name}"

    def identity_key(self) -> str:
        return f"{self.table_key}::uq::{self.constraint_name}::{','.join(self.columns)}"

    def signature(self) -> str:
        return f"UNIQUE ({', '.join(self.columns)})"


@dataclass(frozen=True, order=True)
class CheckConstraintInfo:
    constraint_name: str
    table_schema: str
    table_name: str
    check_clause: str

    @property
    def table_key(self) -> str:
        return f"{self.table_schema}.{self.table_name}"

    def identity_key(self) -> str:
        return f"{self.table_key}::ck::{self.constraint_name}"

    def signature(self) -> str:
        return f"CHECK ({self.check_clause})"


@dataclass(frozen=True, order=True)
class IndexInfo:
    schema_name: str
    table_name: str
    index_name: str
    columns: tuple[str, ...]
    is_unique: bool
    is_primary: bool
    index_definition: str

    @property
    def table_key(self) -> str:
        return f"{self.schema_name}.{self.table_name}"

    def identity_key(self) -> str:
        return f"{self.table_key}::idx::{self.index_name}"

    def signature(self) -> str:
        uniq = "UNIQUE " if self.is_unique else ""
        return f"{uniq}INDEX ({', '.join(self.columns)})"


@dataclass(frozen=True, order=True)
class SequenceInfo:
    sequence_schema: str
    sequence_name: str
    data_type: str
    start_value: str | None = None
    minimum_value: str | None = None
    maximum_value: str | None = None
    increment: str | None = None

    def identity_key(self) -> str:
        return f"{self.sequence_schema}.{self.sequence_name}"

    def signature(self) -> str:
        return (
            f"{self.data_type} start={self.start_value} "
            f"min={self.minimum_value} max={self.maximum_value} inc={self.increment}"
        )


@dataclass
class SchemaSnapshot:
    """Complete schema metadata for one database/schema."""

    label: str
    schema_name: str
    tables: list[TableRef] = field(default_factory=list)
    columns: list[ColumnInfo] = field(default_factory=list)
    primary_keys: list[PrimaryKeyInfo] = field(default_factory=list)
    foreign_keys: list[ForeignKeyInfo] = field(default_factory=list)
    unique_constraints: list[UniqueConstraintInfo] = field(default_factory=list)
    check_constraints: list[CheckConstraintInfo] = field(default_factory=list)
    indexes: list[IndexInfo] = field(default_factory=list)
    sequences: list[SequenceInfo] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiffItem:
    category: str
    status: str  # SAME | ONLY_IN_DB1 | ONLY_IN_DB2 | TYPE_DIFFERENCE
    key: str
    detail_db1: str = ""
    detail_db2: str = ""
    object_db1: Any = None
    object_db2: Any = None


@dataclass
class CategoryDiff:
    category: str
    same: list[DiffItem] = field(default_factory=list)
    only_db1: list[DiffItem] = field(default_factory=list)
    only_db2: list[DiffItem] = field(default_factory=list)
    type_diff: list[DiffItem] = field(default_factory=list)

    @property
    def difference_count(self) -> int:
        return len(self.only_db1) + len(self.only_db2) + len(self.type_diff)


@dataclass
class CompareResult:
    db1_label: str
    db2_label: str
    categories: dict[str, CategoryDiff] = field(default_factory=dict)

    def summary_rows(self) -> list[tuple[str, int, int, int, int]]:
        rows: list[tuple[str, int, int, int, int]] = []
        for name, cat in self.categories.items():
            rows.append(
                (
                    name,
                    len(cat.same),
                    len(cat.only_db1),
                    len(cat.only_db2),
                    len(cat.type_diff),
                )
            )
        return rows
