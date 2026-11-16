"""Connessione a PostGIS (usato solo nella pipeline di build, ADR 0005)."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg

DEFAULT_URL = "postgresql://cordata:cordata-dev@localhost:5432/cordata"


def connect() -> psycopg.Connection:
    """Connessione da `CORDATA_DB_URL` (default: database locale di sviluppo)."""
    return psycopg.connect(os.environ.get("CORDATA_DB_URL", DEFAULT_URL), autocommit=True)


def run_sql_file(conn: psycopg.Connection, path: Path) -> None:
    conn.execute(Path(path).read_text(encoding="utf-8"))
