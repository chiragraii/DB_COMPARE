"""Database connection configuration from env, .env, and CLI overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class DbConfig:
    host: str
    port: int
    database: str
    user: str
    password: str
    schema: str = "public"
    label: str = "DB"

    def dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.database} "
            f"user={self.user} password={self.password}"
        )

    def display(self) -> str:
        return f"{self.label} ({self.host}:{self.port}/{self.database} schema={self.schema})"


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def load_db_config(
    side: str,
    *,
    host: str | None = None,
    port: int | None = None,
    database: str | None = None,
    user: str | None = None,
    password: str | None = None,
    schema: str | None = None,
    label: str | None = None,
    env_file: str | Path | None = None,
) -> DbConfig:
    """Load DB-{side} settings. `side` is '1' or '2'."""

    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    prefix = f"DB{side}_"
    resolved_host = host or _env(f"{prefix}HOST", "localhost")
    resolved_port = port if port is not None else int(_env(f"{prefix}PORT", "5432") or "5432")
    resolved_db = database or _env(f"{prefix}NAME", _env(f"{prefix}DATABASE", "postgres"))
    resolved_user = user or _env(f"{prefix}USER", "postgres")
    resolved_password = password if password is not None else (_env(f"{prefix}PASSWORD", "") or "")
    resolved_schema = schema or _env(f"{prefix}SCHEMA", "public")
    resolved_label = label or _env(f"{prefix}LABEL", f"DB-{side}")

    assert resolved_host and resolved_db and resolved_user and resolved_schema
    return DbConfig(
        host=resolved_host,
        port=resolved_port,
        database=resolved_db,
        user=resolved_user,
        password=resolved_password,
        schema=resolved_schema,
        label=resolved_label or f"DB-{side}",
    )
