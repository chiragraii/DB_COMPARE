"""Fixture schema snapshots for mock/demo mode and unit tests."""

from __future__ import annotations

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


def load_fixture_pair() -> tuple[SchemaSnapshot, SchemaSnapshot]:
    """
    Two intentionally divergent schemas.

    DB-1 (source-like): has PK on orders, FK orders->customers, extra table audit_log
    DB-2 (target-like): missing orders PK/FK, different email column type, extra table payments
    """
    return fixture_db1(), fixture_db2()


def fixture_db1() -> SchemaSnapshot:
    schema = "public"
    return SchemaSnapshot(
        label="DB-1 (fixture)",
        schema_name=schema,
        tables=[
            TableRef(schema, "customers"),
            TableRef(schema, "orders"),
            TableRef(schema, "order_items"),
            TableRef(schema, "audit_log"),
        ],
        columns=[
            ColumnInfo(schema, "customers", "id", "integer", "int4", False, ordinal_position=1),
            ColumnInfo(
                schema,
                "customers",
                "email",
                "character varying",
                "varchar",
                False,
                character_maximum_length=255,
                ordinal_position=2,
            ),
            ColumnInfo(
                schema,
                "customers",
                "name",
                "character varying",
                "varchar",
                True,
                character_maximum_length=100,
                ordinal_position=3,
            ),
            ColumnInfo(schema, "orders", "id", "integer", "int4", False, ordinal_position=1),
            ColumnInfo(
                schema, "orders", "customer_id", "integer", "int4", False, ordinal_position=2
            ),
            ColumnInfo(
                schema, "orders", "total", "numeric", "numeric", False, numeric_precision=12, numeric_scale=2, ordinal_position=3
            ),
            ColumnInfo(schema, "order_items", "id", "integer", "int4", False, ordinal_position=1),
            ColumnInfo(
                schema, "order_items", "order_id", "integer", "int4", False, ordinal_position=2
            ),
            ColumnInfo(
                schema, "order_items", "sku", "character varying", "varchar", False, character_maximum_length=64, ordinal_position=3
            ),
            ColumnInfo(schema, "audit_log", "id", "bigint", "int8", False, ordinal_position=1),
            ColumnInfo(
                schema, "audit_log", "message", "text", "text", True, ordinal_position=2
            ),
        ],
        primary_keys=[
            PrimaryKeyInfo("customers_pkey", schema, "customers", ("id",)),
            PrimaryKeyInfo("orders_pkey", schema, "orders", ("id",)),
            PrimaryKeyInfo("order_items_pkey", schema, "order_items", ("id",)),
            PrimaryKeyInfo("audit_log_pkey", schema, "audit_log", ("id",)),
        ],
        foreign_keys=[
            ForeignKeyInfo(
                "orders_customer_id_fkey",
                schema,
                "orders",
                ("customer_id",),
                schema,
                "customers",
                ("id",),
                on_update="NO ACTION",
                on_delete="CASCADE",
            ),
            ForeignKeyInfo(
                "order_items_order_id_fkey",
                schema,
                "order_items",
                ("order_id",),
                schema,
                "orders",
                ("id",),
                on_update="NO ACTION",
                on_delete="CASCADE",
            ),
        ],
        unique_constraints=[
            UniqueConstraintInfo("customers_email_key", schema, "customers", ("email",)),
        ],
        check_constraints=[
            CheckConstraintInfo(
                "orders_total_positive",
                schema,
                "orders",
                "((total >= (0)::numeric))",
            ),
        ],
        indexes=[
            IndexInfo(
                schema,
                "orders",
                "idx_orders_customer_id",
                ("customer_id",),
                False,
                False,
                "CREATE INDEX idx_orders_customer_id ON public.orders USING btree (customer_id)",
            ),
        ],
        sequences=[
            SequenceInfo(schema, "customers_id_seq", "bigint", "1", "1", "9223372036854775807", "1"),
            SequenceInfo(schema, "orders_id_seq", "bigint", "1", "1", "9223372036854775807", "1"),
        ],
    )


def fixture_db2() -> SchemaSnapshot:
    schema = "public"
    return SchemaSnapshot(
        label="DB-2 (fixture)",
        schema_name=schema,
        tables=[
            TableRef(schema, "customers"),
            TableRef(schema, "orders"),
            TableRef(schema, "order_items"),
            TableRef(schema, "payments"),
        ],
        columns=[
            ColumnInfo(schema, "customers", "id", "integer", "int4", False, ordinal_position=1),
            # TYPE DIFFERENCE: text instead of varchar(255), and nullable
            ColumnInfo(
                schema,
                "customers",
                "email",
                "text",
                "text",
                True,
                ordinal_position=2,
            ),
            ColumnInfo(
                schema,
                "customers",
                "name",
                "character varying",
                "varchar",
                True,
                character_maximum_length=100,
                ordinal_position=3,
            ),
            ColumnInfo(schema, "orders", "id", "integer", "int4", False, ordinal_position=1),
            ColumnInfo(
                schema, "orders", "customer_id", "integer", "int4", False, ordinal_position=2
            ),
            ColumnInfo(
                schema, "orders", "total", "numeric", "numeric", False, numeric_precision=12, numeric_scale=2, ordinal_position=3
            ),
            ColumnInfo(schema, "order_items", "id", "integer", "int4", False, ordinal_position=1),
            ColumnInfo(
                schema, "order_items", "order_id", "integer", "int4", False, ordinal_position=2
            ),
            ColumnInfo(
                schema, "order_items", "sku", "character varying", "varchar", False, character_maximum_length=64, ordinal_position=3
            ),
            ColumnInfo(schema, "payments", "id", "integer", "int4", False, ordinal_position=1),
            ColumnInfo(
                schema, "payments", "order_id", "integer", "int4", False, ordinal_position=2
            ),
            ColumnInfo(
                schema, "payments", "amount", "numeric", "numeric", False, numeric_precision=12, numeric_scale=2, ordinal_position=3
            ),
        ],
        primary_keys=[
            PrimaryKeyInfo("customers_pkey", schema, "customers", ("id",)),
            # MISSING: orders_pkey
            PrimaryKeyInfo("order_items_pkey", schema, "order_items", ("id",)),
            PrimaryKeyInfo("payments_pkey", schema, "payments", ("id",)),
        ],
        foreign_keys=[
            # MISSING: orders_customer_id_fkey
            ForeignKeyInfo(
                "order_items_order_id_fkey",
                schema,
                "order_items",
                ("order_id",),
                schema,
                "orders",
                ("id",),
                on_update="NO ACTION",
                on_delete="CASCADE",
            ),
            ForeignKeyInfo(
                "payments_order_id_fkey",
                schema,
                "payments",
                ("order_id",),
                schema,
                "orders",
                ("id",),
                on_update="NO ACTION",
                on_delete="RESTRICT",
            ),
        ],
        unique_constraints=[
            # MISSING customers_email_key — instead different unique on payments
            UniqueConstraintInfo("payments_order_id_key", schema, "payments", ("order_id",)),
        ],
        check_constraints=[
            # TYPE DIFFERENCE on check clause vs DB-1
            CheckConstraintInfo(
                "orders_total_positive",
                schema,
                "orders",
                "((total > (0)::numeric))",
            ),
        ],
        indexes=[
            # MISSING idx_orders_customer_id
            IndexInfo(
                schema,
                "payments",
                "idx_payments_amount",
                ("amount",),
                False,
                False,
                "CREATE INDEX idx_payments_amount ON public.payments USING btree (amount)",
            ),
        ],
        sequences=[
            SequenceInfo(schema, "customers_id_seq", "bigint", "1", "1", "9223372036854775807", "1"),
            SequenceInfo(schema, "orders_id_seq", "bigint", "1", "1", "9223372036854775807", "1"),
            SequenceInfo(schema, "payments_id_seq", "bigint", "1", "1", "9223372036854775807", "1"),
        ],
    )
