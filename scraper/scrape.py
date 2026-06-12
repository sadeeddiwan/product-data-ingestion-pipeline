"""
scraper/scrape.py
=================
Extracts product data from books.toscrape.com using Requests + BeautifulSoup4.

Collected fields per book:
  - title        : Full book title
  - price_raw    : Raw price string (e.g. "£12.99") — cleaned downstream
  - availability : Stock status string
  - rating       : Integer star rating (1–5)

Output: data/raw/books_raw.csv
"""

import time
import logging
import os

import requests
from bs4 import BeautifulSoup
import pandas as pd

# Import project config — works whether run directly or as a package
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    SCRAPE_BASE_URL,
    SCRAPE_MAX_PAGES,
    SCRAPE_DELAY,
    REQUEST_TIMEOUT,
    RATING_MAP,
    RAW_CSV_PATH,
    RAW_DIR,
)

logger = logging.getLogger(__name__)


# ── HTTP helpers ──────────────────────────────────────────────────────────────

_SESSION = requests.Session()
_SESSION.headers.update(
    {
        # A realistic browser UA avoids bot-detection blocks on many sites.
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    }
)


def _fetch_page(url: str) -> BeautifulSoup | None:
    """
    Fetch a single catalogue page and return a parsed BeautifulSoup object.

    Uses a persistent Session with a browser-like User-Agent header to avoid
    being blocked by basic bot-detection systems.

    Returns None on any network or HTTP error so the caller can skip the page
    gracefully rather than crashing the whole run.
    """
    try:
        response = _SESSION.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        logger.debug(f"HTTP 200 → {url}")
        return BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error for {url}: {e}")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error for {url}: {e}")
    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching {url} (>{REQUEST_TIMEOUT}s)")
    except requests.exceptions.RequestException as e:
        logger.error(f"Unexpected request error for {url}: {e}")
    return None


# ── Page parsers ──────────────────────────────────────────────────────────────

def _parse_books(soup: BeautifulSoup) -> list[dict]:
    """
    Extract all books from a parsed catalogue page.

    HTML structure of each book card:
        <article class="product_pod">
          <p class="star-rating Three"></p>
          <h3><a title="Full Title">Short Title...</a></h3>
          <p class="price_color">£12.99</p>
          <p class="availability">In stock</p>
        </article>

    Returns a list of raw dicts — no type conversion yet.
    """
    books = []

    for article in soup.select("article.product_pod"):
        # --- Title ---
        title_tag = article.select_one("h3 a")
        title = title_tag["title"].strip() if title_tag and title_tag.has_attr("title") else "Unknown"

        # --- Raw price (currency symbol kept for audit trail) ---
        price_tag = article.select_one("p.price_color")
        price_raw = price_tag.text.strip() if price_tag else ""

        # --- Availability ---
        avail_tag = article.select_one("p.availability")
        availability = avail_tag.text.strip() if avail_tag else "Unknown"

        # --- Star rating (encoded as CSS class: "One", "Two", …) ---
        rating_tag = article.select_one("p.star-rating")
        if rating_tag:
            # class list is e.g. ["star-rating", "Three"]
            classes = rating_tag.get("class", [])
            rating_word = classes[1] if len(classes) > 1 else "Zero"
        else:
            rating_word = "Zero"
        rating = RATING_MAP.get(rating_word, 0)

        books.append(
            {
                "title":        title,
                "price_raw":    price_raw,
                "availability": availability,
                "rating":       rating,
            }
        )

    return books


def _get_next_page_url(soup: BeautifulSoup) -> str | None:
    """
    Return the absolute URL of the next catalogue page, or None on the last page.

    books.toscrape.com uses relative hrefs like "page-2.html" on page 1 but
    "catalogue/page-3.html" on page 2+, so we always prepend the base URL and
    strip any leading path segment that duplicates it.
    """
    next_btn = soup.select_one("li.next a")
    if not next_btn:
        return None

    href = next_btn["href"]
    # href on page 1 → "catalogue/page-2.html"
    # href on page 2+ → "page-3.html"
    if href.startswith("catalogue/"):
        return "http://books.toscrape.com/" + href
    return SCRAPE_BASE_URL + href


# ── Public API ────────────────────────────────────────────────────────────────

def scrape_books(max_pages: int = SCRAPE_MAX_PAGES) -> str:
    """
    Scrape book product data from books.toscrape.com and save to CSV.

    Iterates through up to ``max_pages`` catalogue pages, collecting one row
    per book.  A 0.5-second delay between requests keeps the scraper polite.

    Args:
        max_pages: Upper bound on the number of pages to scrape.
                   The live site has exactly 50 pages (1 000 books).

    Returns:
        Absolute path to the saved raw CSV file.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    all_books: list[dict] = []
    current_url: str | None = SCRAPE_BASE_URL + "page-1.html"
    page_num = 1

    logger.info(f"Scrape starting — target: {SCRAPE_BASE_URL}  max_pages={max_pages}")

    while current_url and page_num <= max_pages:
        logger.info(f"[Page {page_num:>2}/{max_pages}] {current_url}")

        soup = _fetch_page(current_url)
        if soup is None:
            logger.warning(f"Skipping page {page_num} — fetch failed.")
            break

        books = _parse_books(soup)
        all_books.extend(books)
        logger.info(f"  → collected {len(books)} books  (running total: {len(all_books)})")

        current_url = _get_next_page_url(soup)
        page_num += 1

        if current_url:                   # no delay after the final page
            time.sleep(SCRAPE_DELAY)

    # ── Persist raw data ──────────────────────────────────────────────────────
    df = pd.DataFrame(all_books)
    df.to_csv(RAW_CSV_PATH, index=False, encoding="utf-8")

    logger.info(
        f"Scrape complete — {len(df)} records saved to '{RAW_CSV_PATH}'"
    )
    return str(RAW_CSV_PATH)
