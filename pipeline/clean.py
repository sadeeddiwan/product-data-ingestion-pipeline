"""
pipeline/clean.py
=================
Transforms raw scraped data into an analysis-ready, strongly-typed dataset.

Cleaning steps applied in order:
  1. Parse price  → strip currency symbol, cast to float
  2. Normalise availability  → "In Stock" | "Out of Stock"
  3. Strip whitespace from title strings
  4. Coerce rating to int (guard against NaN from scraper edge-cases)
  5. Drop original raw columns
  6. Validate each record (price > 0, title present, rating in 1–5)
  7. Deduplicate on title (keep first occurrence)
  8. Enforce final column order

Output: data/processed/books_clean.csv
"""

import re
import logging
import os

import pandas as pd

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RAW_CSV_PATH, CLEAN_CSV_PATH, PROCESSED_DIR

logger = logging.getLogger(__name__)


# ── Field-level transformers ──────────────────────────────────────────────────

def _parse_price(raw: str) -> float | None:
    """
    Strip any non-numeric characters (£, €, whitespace, …) and return a float.

    Returns None when the value cannot be parsed — these rows are later
    rejected by the validator.

    Examples:
        "£12.99"  →  12.99
        "Â£51.77" →  51.77   (mojibake variant seen on some scrapers)
        ""        →  None
    """
    if pd.isna(raw) or str(raw).strip() == "":
        return None
    try:
        numeric_str = re.sub(r"[^\d.]", "", str(raw))
        return round(float(numeric_str), 2) if numeric_str else None
    except (ValueError, TypeError):
        return None


def _normalise_availability(raw: str) -> str:
    """
    Map the scraped availability text to one of two canonical values.

    books.toscrape.com uses "In stock" (with variable whitespace / newlines),
    so a case-insensitive substring check is the safest approach.
    """
    if "in stock" in str(raw).lower():
        return "In Stock"
    return "Out of Stock"


# ── Row-level validator ───────────────────────────────────────────────────────

def _is_valid(row: pd.Series) -> bool:
    """
    Return True when a record passes all data-quality rules.

    Rules:
      - price must be a positive, finite number
      - title must be a non-empty string that isn't the sentinel "Unknown"
      - rating must be an integer in the 1–5 range
    """
    if pd.isna(row["price"]) or row["price"] <= 0:
        return False
    if not str(row["title"]).strip() or str(row["title"]).strip() == "Unknown":
        return False
    if int(row["rating"]) not in (1, 2, 3, 4, 5):
        return False
    return True


# ── Public API ────────────────────────────────────────────────────────────────

def clean_data(raw_path: str) -> str:
    """
    Load a raw CSV, apply cleaning & validation, and persist the result.

    Args:
        raw_path: Path to the raw CSV produced by the scraper.

    Returns:
        Absolute path to the cleaned CSV file.

    Raises:
        FileNotFoundError: If ``raw_path`` does not exist.
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # ── Load ──────────────────────────────────────────────────────────────────
    df = pd.read_csv(raw_path, encoding="utf-8")
    initial_count = len(df)
    logger.info(f"Loaded {initial_count} raw records from '{raw_path}'")

    # ── Transform ─────────────────────────────────────────────────────────────
    logger.info("Applying transformations …")

    df["price"]        = df["price_raw"].apply(_parse_price)
    df["availability"] = df["availability"].apply(_normalise_availability)
    df["title"]        = df["title"].astype(str).str.strip()
    df["rating"]       = pd.to_numeric(df["rating"], errors="coerce") \
                                       .fillna(0).astype(int)

    # Drop the raw price column — clean version takes its place
    df.drop(columns=["price_raw"], inplace=True)

    # ── Validate ──────────────────────────────────────────────────────────────
    valid_mask = df.apply(_is_valid, axis=1)
    n_invalid  = (~valid_mask).sum()
    df         = df[valid_mask].copy()
    logger.info(f"Validation: {n_invalid} records dropped, {len(df)} retained")

    # Log a breakdown of why records were dropped (helpful for debugging)
    if n_invalid > 0:
        logger.debug("Invalid record sample (first 5):")
        logger.debug(df[~valid_mask].head().to_string())

    # ── Deduplicate ───────────────────────────────────────────────────────────
    before_dedup = len(df)
    df.drop_duplicates(subset=["title"], keep="first", inplace=True)
    dupes_removed = before_dedup - len(df)
    if dupes_removed:
        logger.info(f"Deduplication: removed {dupes_removed} duplicate titles")
    else:
        logger.info("Deduplication: no duplicates found")

    # ── Enforce column order ──────────────────────────────────────────────────
    df = df[["title", "price", "rating", "availability"]].reset_index(drop=True)

    # ── Summary stats ─────────────────────────────────────────────────────────
    logger.info(
        f"Clean dataset — "
        f"rows: {len(df)}  |  "
        f"avg_price: £{df['price'].mean():.2f}  |  "
        f"price_range: £{df['price'].min():.2f}–£{df['price'].max():.2f}  |  "
        f"in_stock: {(df['availability']=='In Stock').sum()}"
    )

    # ── Persist ───────────────────────────────────────────────────────────────
    df.to_csv(CLEAN_CSV_PATH, index=False, encoding="utf-8")
    logger.info(f"Cleaned data saved to '{CLEAN_CSV_PATH}'")

    return str(CLEAN_CSV_PATH)
