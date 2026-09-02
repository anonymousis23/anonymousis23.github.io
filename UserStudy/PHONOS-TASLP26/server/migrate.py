#!/usr/bin/env python3
"""Apply the response API schema to SQLite or PostgreSQL."""

from __future__ import annotations

import os


if os.getenv("DATABASE_URL_UNPOOLED"):
    os.environ["DATABASE_URL"] = os.environ["DATABASE_URL_UNPOOLED"]
os.environ["AUTO_CREATE_SCHEMA"] = "0"

from app import DATABASE_URL, engine, migrate_database  # noqa: E402


def main() -> None:
    migrate_database()
    print(f"Schema is current on {engine.dialect.name}: {DATABASE_URL.split('@')[-1]}")


if __name__ == "__main__":
    main()
