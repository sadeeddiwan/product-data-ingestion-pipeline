"""
config.py
=========
Centralised configuration for the Product Data Ingestion Pipeline.
All paths, constants, and settings are defined here for easy modification.
"""

from pathlib import Path

# ── Directory Layout ──────────────────────────────────────────────────────────
ROOT_DIR      = Path(__file__).parent
DATA_DIR      = ROOT_DIR / "data"
RAW_DIR       = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
DB_DIR        = DATA_DIR / "db"
LOG_DIR       = ROOT_DIR / "logs"

# ── File Paths ────────────────────────────────────────────────────────────────
RAW_CSV_PATH   = RAW_DIR       / "books_raw.csv"
CLEAN_CSV_PATH = PROCESSED_DIR / "books_clean.csv"
DB_PATH        = DB_DIR        / "books.db"
LOG_PATH       = LOG_DIR       / "pipeline.log"

# ── Scraper Settings ──────────────────────────────────────────────────────────
SCRAPE_BASE_URL  = "http://books.toscrape.com/catalogue/"
SCRAPE_MAX_PAGES = 50          # books.toscrape.com has exactly 50 pages (1 000 books)
SCRAPE_DELAY     = 0.5         # seconds between requests — polite crawling
REQUEST_TIMEOUT  = 10          # seconds before a request is abandoned

# ── Rating Mapping ────────────────────────────────────────────────────────────
# books.toscrape.com encodes star-ratings as CSS class names (English words)
RATING_MAP = {
    "One":   1,
    "Two":   2,
    "Three": 3,
    "Four":  4,
    "Five":  5,
}

# ── SQLite Table ──────────────────────────────────────────────────────────────
DB_TABLE = "books"
