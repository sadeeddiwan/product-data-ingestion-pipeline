"""
analytics/queries.py
====================
Executes analytical SQL queries against the SQLite "books" table and returns
results as pandas DataFrames.

Each query function is independently callable, making the module easy to
unit-test and reuse in notebooks or other reporting tools.

The ``run_analytics`` entry-point executes all queries, logs results, and
returns a consolidated dictionary for the dashboard to consume.
"""

import logging
import os
import sqlite3

import pandas as pd

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH, DB_TABLE

logger = logging.getLogger(__name__)


# ── Connection helper ─────────────────────────────────────────────────────────

def _connect(db_path: str) -> sqlite3.Connection:
    """Open a read-only-safe SQLite connection."""
    return sqlite3.connect(db_path)


# ── Individual analytics queries ──────────────────────────────────────────────

def q_product_count(conn: sqlite3.Connection) -> pd.DataFrame:
    """Total number of products ingested."""
    return pd.read_sql(
        f"SELECT COUNT(*) AS total_products FROM {DB_TABLE};",
        conn,
    )


def q_average_price(conn: sqlite3.Connection) -> pd.DataFrame:
    """Mean product price across the full catalogue."""
    return pd.read_sql(
        f"SELECT ROUND(AVG(price), 2) AS avg_price FROM {DB_TABLE};",
        conn,
    )


def q_products_by_rating(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Number of products and average price grouped by star rating (1–5).
    Ordered highest-to-lowest for dashboard display.
    """
    return pd.read_sql(
        f"""
        SELECT
            rating,
            COUNT(*)              AS product_count,
            ROUND(AVG(price), 2)  AS avg_price,
            ROUND(MIN(price), 2)  AS min_price,
            ROUND(MAX(price), 2)  AS max_price
        FROM   {DB_TABLE}
        GROUP  BY rating
        ORDER  BY rating DESC;
        """,
        conn,
    )


def q_availability_summary(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Count and percentage share for each availability status.
    """
    return pd.read_sql(
        f"""
        SELECT
            availability,
            COUNT(*)                                              AS count,
            ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)   AS pct
        FROM   {DB_TABLE}
        GROUP  BY availability;
        """,
        conn,
    )


def q_top10_expensive(conn: sqlite3.Connection) -> pd.DataFrame:
    """Top 10 most expensive products with all key attributes."""
    return pd.read_sql(
        f"""
        SELECT
            title,
            price,
            rating,
            availability
        FROM   {DB_TABLE}
        ORDER  BY price DESC
        LIMIT  10;
        """,
        conn,
    )


def q_price_distribution(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Books bucketed into £10 price bands for histogram-style analysis.
    Ordered by the lower bound of each band.
    """
    return pd.read_sql(
        f"""
        SELECT
            CASE
                WHEN price <  10 THEN '£0–10'
                WHEN price <  20 THEN '£10–20'
                WHEN price <  30 THEN '£20–30'
                WHEN price <  40 THEN '£30–40'
                WHEN price <  50 THEN '£40–50'
                ELSE                   '£50+'
            END          AS price_band,
            COUNT(*)     AS count,
            MIN(price)   AS band_min   -- used for ORDER BY only
        FROM   {DB_TABLE}
        GROUP  BY price_band
        ORDER  BY band_min;
        """,
        conn,
    )


def q_rating_price_heatmap(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Cross-tabulation of rating × availability with average price —
    useful for a heatmap or pivot table in the dashboard.
    """
    return pd.read_sql(
        f"""
        SELECT
            rating,
            availability,
            COUNT(*)             AS count,
            ROUND(AVG(price), 2) AS avg_price
        FROM   {DB_TABLE}
        GROUP  BY rating, availability
        ORDER  BY rating, availability;
        """,
        conn,
    )


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_analytics(db_path: str = str(DB_PATH)) -> dict[str, pd.DataFrame]:
    """
    Execute all analytics queries and return results as a labelled dict.

    Each key maps to the corresponding DataFrame, e.g.:

        results["top10_expensive"]   # → DataFrame with 10 rows

    Results are also logged at INFO level so pipeline runs are self-documenting
    even when the Streamlit dashboard is not open.

    Args:
        db_path: Path to the SQLite database.

    Returns:
        Dict mapping query names to DataFrames.
    """
    conn = _connect(db_path)
    logger.info(f"Running analytics against '{db_path}'")

    query_registry = {
        "product_count":        q_product_count,
        "average_price":        q_average_price,
        "products_by_rating":   q_products_by_rating,
        "availability_summary": q_availability_summary,
        "top10_expensive":      q_top10_expensive,
        "price_distribution":   q_price_distribution,
        "rating_price_heatmap": q_rating_price_heatmap,
    }

    results: dict[str, pd.DataFrame] = {}

    for name, fn in query_registry.items():
        try:
            df = fn(conn)
            results[name] = df
            logger.info(f"\n{'─'*50}\n[{name}]\n{df.to_string(index=False)}")
        except Exception as exc:
            logger.error(f"Query '{name}' failed: {exc}")
            results[name] = pd.DataFrame()   # empty placeholder

    conn.close()
    logger.info("All analytics queries complete.")
    return results
