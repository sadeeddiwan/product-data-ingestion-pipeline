"""
main.py
=======
Entry point for the Product Data Ingestion Pipeline.

Orchestration order:
  1. Scrape  → books.toscrape.com  →  data/raw/books_raw.csv
  2. Clean   → validate & transform →  data/processed/books_clean.csv
  3. Load    → SQLite ingestion     →  data/db/books.db
  4. Analyse → SQL analytics layer  →  logged to console + logs/pipeline.log

Usage:
    python main.py
"""

import logging
import os
import sys
import time
from pathlib import Path

# ── Ensure project root is on sys.path ────────────────────────────────────────
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from config import LOG_DIR, LOG_PATH


# ── Logging configuration ─────────────────────────────────────────────────────
def _configure_logging() -> None:
    """
    Set up the root logger with two handlers:
      - StreamHandler  : coloured, human-readable console output
      - FileHandler    : structured append-mode log file
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_format = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            # Console — always show INFO+
            logging.StreamHandler(sys.stdout),
            # File — persist full run history (append mode)
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
        ],
    )

    # Quieten noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


# ── Pipeline stages ───────────────────────────────────────────────────────────

def _stage(logger: logging.Logger, num: int, name: str) -> None:
    """Log a visible stage banner."""
    logger.info("")
    logger.info(f"{'═'*60}")
    logger.info(f"  STAGE {num}: {name}")
    logger.info(f"{'═'*60}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run_pipeline() -> str:
    """
    Execute all four pipeline stages sequentially.

    Returns:
        Path to the populated SQLite database.
    """
    _configure_logging()
    logger = logging.getLogger(__name__)

    # Late imports so logging is configured before any module-level loggers fire
    from scraper.scrape   import scrape_books
    from pipeline.clean   import clean_data
    from pipeline.load    import load_to_sqlite
    from analytics.queries import run_analytics

    start_time = time.time()

    logger.info("")
    logger.info("╔══════════════════════════════════════════════════════════╗")
    logger.info("║       PRODUCT DATA INGESTION PIPELINE — START            ║")
    logger.info("╚══════════════════════════════════════════════════════════╝")

    # ── Stage 1: Scrape ───────────────────────────────────────────────────────
    _stage(logger, 1, "SCRAPE — books.toscrape.com")
    t0 = time.time()
    raw_path = scrape_books()
    logger.info(f"Stage 1 done in {time.time()-t0:.1f}s  →  {raw_path}")

    # ── Stage 2: Clean ────────────────────────────────────────────────────────
    _stage(logger, 2, "CLEAN & VALIDATE")
    t0 = time.time()
    clean_path = clean_data(raw_path)
    logger.info(f"Stage 2 done in {time.time()-t0:.1f}s  →  {clean_path}")

    # ── Stage 3: Load ─────────────────────────────────────────────────────────
    _stage(logger, 3, "LOAD → SQLite")
    t0 = time.time()
    db_path = load_to_sqlite(clean_path)
    logger.info(f"Stage 3 done in {time.time()-t0:.1f}s  →  {db_path}")

    # ── Stage 4: Analyse ──────────────────────────────────────────────────────
    _stage(logger, 4, "SQL ANALYTICS")
    t0 = time.time()
    run_analytics(db_path)
    logger.info(f"Stage 4 done in {time.time()-t0:.1f}s")

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    logger.info("")
    logger.info("╔══════════════════════════════════════════════════════════╗")
    logger.info(f"║  PIPELINE COMPLETE  —  total elapsed: {elapsed:>6.1f}s          ║")
    logger.info("╚══════════════════════════════════════════════════════════╝")
    logger.info(f"  Dashboard: streamlit run dashboard/app.py")
    logger.info("")

    return db_path


if __name__ == "__main__":
    run_pipeline()
