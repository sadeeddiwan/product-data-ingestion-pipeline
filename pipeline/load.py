"""
pipeline/load.py
================
Ingests a cleaned CSV into the SQLite "books" table.

Design decisions:
  - Full truncate-and-reload on every run (idempotent; suits a daily batch).
  - AUTOINCREMENT surrogate key so downstream joins remain stable.
  - ``loaded_at`` column records the ingestion timestamp for lineage tracking.
  - pandas.DataFrame.to_sql uses append mode after clearing the table, giving
    us bulk-insert performance without losing the DDL-managed surrogate key.
"""

import logging
import os
import sqlite3

import pandas as pd

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CLEAN_CSV_PATH, DB_PATH, DB_DIR, DB_TABLE

logger = logging.getLogger(__name__)


# ── DDL ───────────────────────────────────────────────────────────────────────

_CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {DB_TABLE} (
    id            INTEGER  PRIMARY KEY AUTOINCREMENT,
    title         TEXT     NOT NULL UNIQUE,
    price         REAL     NOT NULL,
    rating        INTEGER  NOT NULL  CHECK (rating BETWEEN 1 AND 5),
    availability  TEXT     NOT NULL,
    loaded_at     DATETIME DEFAULT  CURRENT_TIMESTAMP
);
"""

_CREATE_IDX_PRICE_SQL  = f"CREATE INDEX IF NOT EXISTS idx_price    ON {DB_TABLE}(price);"
_CREATE_IDX_RATING_SQL = f"CREATE INDEX IF NOT EXISTS idx_rating   ON {DB_TABLE}(rating);"
_CREATE_IDX_AVAIL_SQL  = f"CREATE INDEX IF NOT EXISTS idx_avail    ON {DB_TABLE}(availability);"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _init_schema(conn: sqlite3.Connection) -> None:
    """Create the books table and supporting indexes if they do not yet exist."""
    cursor = conn.cursor()
    cursor.executescript(
        _CREATE_TABLE_SQL
        + _CREATE_IDX_PRICE_SQL
        + _CREATE_IDX_RATING_SQL
        + _CREATE_IDX_AVAIL_SQL
    )
    conn.commit()
    logger.debug("Schema initialised (CREATE IF NOT EXISTS)")


def _truncate(conn: sqlite3.Connection) -> int:
    """Delete all rows from the books table and return the count removed."""
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {DB_TABLE};")
    deleted = cursor.rowcount
    conn.commit()
    logger.info(f"Truncated '{DB_TABLE}': {deleted} existing rows removed")
    return deleted


def _bulk_insert(df: pd.DataFrame, conn: sqlite3.Connection) -> None:
    """
    Bulk-insert the DataFrame into SQLite using pandas.

    We use ``if_exists='append'`` because the table is already created via
    _init_schema; pandas would otherwise drop and recreate it without our DDL
    constraints (CHECK, UNIQUE, AUTOINCREMENT).
    """
    # Only insert the columns the table expects (drop any extras)
    cols = ["title", "price", "rating", "availability"]
    df[cols].to_sql(DB_TABLE, conn, if_exists="append", index=False, method="multi")
    logger.debug(f"Inserted {len(df)} rows via pandas bulk insert")


# ── Public API ────────────────────────────────────────────────────────────────

def load_to_sqlite(
    clean_path: str = str(CLEAN_CSV_PATH),
    db_path: str    = str(DB_PATH),
) -> str:
    """
    Load a cleaned CSV file into the SQLite ``books`` table.

    The operation is idempotent: each invocation truncates the table before
    reloading, so re-running the pipeline never creates duplicate rows.

    Args:
        clean_path : Path to the cleaned CSV (output of ``pipeline.clean``).
        db_path    : Path to the SQLite database file. Created if absent.

    Returns:
        Absolute path to the SQLite database file.
    """
    DB_DIR.mkdir(parents=True, exist_ok=True)

    # ── Read source ───────────────────────────────────────────────────────────
    df = pd.read_csv(clean_path, encoding="utf-8")
    logger.info(f"Read {len(df)} clean records from '{clean_path}'")

    # ── Connect & initialise ──────────────────────────────────────────────────
    conn = sqlite3.connect(db_path)
    logger.info(f"Connected to SQLite at '{db_path}'")

    try:
        _init_schema(conn)
        _truncate(conn)
        _bulk_insert(df, conn)

        # ── Verify ────────────────────────────────────────────────────────────
        cursor = conn.cursor()
        row_count = cursor.execute(f"SELECT COUNT(*) FROM {DB_TABLE}").fetchone()[0]
        logger.info(
            f"Load complete — '{DB_TABLE}' table now contains {row_count} rows"
        )

        if row_count != len(df):
            logger.warning(
                f"Row count mismatch: expected {len(df)}, got {row_count}. "
                "Possible UNIQUE constraint violations caused some rows to be skipped."
            )

    finally:
        conn.close()

    return db_path
