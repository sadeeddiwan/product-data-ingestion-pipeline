# 📦 Product Data Ingestion Pipeline

A portfolio-grade end-to-end ETL pipeline built with Python that extracts product data from the web, validates and transforms it, stores it in a relational database, performs SQL-based analytics, and visualizes insights through an interactive Streamlit dashboard.

Key Highlights
Scraped and processed 999+ product records from a real-world website
Built a complete ETL workflow (Extract → Transform → Load)
Implemented data validation, cleaning, deduplication, and quality checks
Loaded structured data into SQLite with indexing and constraints
Created reusable SQL analytics queries for business insights
Developed an interactive dashboard using Streamlit and Plotly
Added filtering, search, CSV export, and pipeline execution from the UI

Tech Stack: Python · Requests · BeautifulSoup4 · Pandas · SQLite · SQL · Streamlit · Plotly

Built as a Data Engineering portfolio project for Werkstudent and Junior Data Engineer opportunities in Germany.

---

## 📐 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     INGESTION PIPELINE                          │
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │  SCRAPE  │───▶│  CLEAN   │───▶│   LOAD   │───▶│ANALYTICS │  │
│  │          │    │          │    │          │    │          │  │
│  │Requests  │    │ Pandas   │    │ SQLite   │    │  SQL     │  │
│  │BS4       │    │ Validate │    │ Bulk ins.│    │ Queries  │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│       │               │               │               │        │
│  books_raw.csv  books_clean.csv   books.db       DataFrames    │
└─────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
                              ┌─────────────────────────┐
                              │   STREAMLIT DASHBOARD    │
                              │  KPIs · Charts · Tables  │
                              └─────────────────────────┘
```

## 🗂 Project Structure

```
product_pipeline/
│
├── scraper/
│   └── scrape.py          # Requests + BS4 scraper (books.toscrape.com)
│
├── pipeline/
│   ├── clean.py           # Pandas cleaning & validation
│   └── load.py            # SQLite ingestion (truncate-and-reload)
│
├── analytics/
│   └── queries.py         # SQL analytics query library
│
├── dashboard/
│   └── app.py             # Streamlit dashboard (KPIs, charts, tables)
│
├── data/
│   ├── raw/               # books_raw.csv   (auto-generated)
│   ├── processed/         # books_clean.csv (auto-generated)
│   └── db/                # books.db        (auto-generated)
│
├── logs/                  # pipeline.log    (auto-generated)
│
├── .streamlit/
│   └── config.toml        # Dashboard theme (dark mode)
│
├── config.py              # Centralised configuration
├── main.py                # Pipeline orchestrator
├── requirements.txt
├── README.md
└── .gitignore
```

---

## ⚙️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Scraping | `requests` + `beautifulsoup4` | HTTP + HTML parsing |
| Processing | `pandas` | Cleaning, validation, transformation |
| Storage | `sqlite3` (stdlib) | Relational store + SQL analytics |
| Visualisation | `streamlit` + `plotly` | Interactive dashboard |
| Logging | `logging` (stdlib) | Structured pipeline observability |

---

## 🚀 Quick Start

### 1 — Clone & install

```bash
git clone https://github.com/your-username/product-pipeline.git
cd product-pipeline
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2 — Run the pipeline

```bash
python main.py
```

This will:
1. Scrape **1 000 books** from [books.toscrape.com](http://books.toscrape.com) (~2 min)
2. Clean and validate the data with Pandas
3. Load into SQLite (`data/db/books.db`)
4. Execute and log 7 SQL analytics queries

### 3 — Launch the dashboard

```bash
streamlit run dashboard/app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 📊 Pipeline Stages

### Stage 1 — Scrape (`scraper/scrape.py`)

Iterates all 50 catalogue pages on `books.toscrape.com`, extracting per-book:

| Field | Raw value | Example |
|-------|-----------|---------|
| `title` | `h3 > a[title]` | "A Light in the Attic" |
| `price_raw` | `p.price_color` | "£51.77" |
| `availability` | `p.availability` | "In stock" |
| `rating` | `p.star-rating[class]` | "Three" → `3` |

Output: `data/raw/books_raw.csv`

### Stage 2 — Clean (`pipeline/clean.py`)

| Transformation | Detail |
|----------------|--------|
| Price parsing | Strip `£`, cast to `float`, round to 2 d.p. |
| Availability normalisation | `"In stock\n  "` → `"In Stock"` |
| Rating coercion | `"Three"` → `3` (int) |
| Validation | Drop rows where price ≤ 0, title missing, or rating ∉ {1–5} |
| Deduplication | Keep first occurrence per unique title |

Output: `data/processed/books_clean.csv`

### Stage 3 — Load (`pipeline/load.py`)

- Creates `books` table (DDL with `UNIQUE`, `CHECK`, `AUTOINCREMENT`)
- Creates indexes on `price`, `rating`, `availability`
- Truncates then bulk-inserts on every run (**idempotent**)
- Logs row-count verification

Output: `data/db/books.db`

### Stage 4 — Analytics (`analytics/queries.py`)

| Query | Description |
|-------|-------------|
| `product_count` | Total books ingested |
| `average_price` | Mean price across catalogue |
| `products_by_rating` | Count + avg/min/max price per star |
| `availability_summary` | In Stock vs Out of Stock with % share |
| `top10_expensive` | 10 highest-priced books |
| `price_distribution` | Books per £10 price band |
| `rating_price_heatmap` | Rating × Availability cross-tab |

---

## 📈 Dashboard Features

Executive KPIs

Total products

Average product price

Inventory availability percentage

Most common product rating

Analytics & Visualization

Product distribution by rating

Price distribution across ranges

Average price by rating

Price range analysis (minimum, average, maximum)

Top 10 most expensive products

Price vs Rating relationship analysis

Data Exploration

Search by title

Filter by rating

Filter by availability

Filter by price range

Download filtered data as CSV

Operational Features

Trigger full ETL pipeline from the dashboard

Refresh cached data

Real-time pipeline execution logs

## 💼 Skills Demonstrated

Data Engineering

ETL Pipeline Design

Data Validation & Cleaning

Relational Database Design

SQL Analytics

Data Modeling

Programming

Python

Pandas

SQLite

Web Scraping

Data Processing

Visualization

Streamlit

Plotly

Interactive Dashboards

KPI Reporting

Software Engineering

Modular Architecture

Logging & Monitoring

Configuration Management

Documentation---

## 🔧 Configuration

All settings are in `config.py`:

```python
SCRAPE_MAX_PAGES = 50     # set lower (e.g. 5) for quick testing
SCRAPE_DELAY     = 0.5    # seconds between page requests
REQUEST_TIMEOUT  = 10     # seconds before abandoning a request
```

---

## 🧪 Testing the Scraper (quick mode)

```bash
# Scrape only 3 pages (~60 books) for fast iteration
python -c "
from scraper.scrape import scrape_books
scrape_books(max_pages=3)
"
```

---

## 📁 Data Lineage

```
books.toscrape.com
       │  HTTP GET (Requests)
       ▼
data/raw/books_raw.csv          ← Stage 1 output (audit trail)
       │  clean_data()
       ▼
data/processed/books_clean.csv  ← Stage 2 output (validated)
       │  load_to_sqlite()
       ▼
data/db/books.db  →  TABLE books (title, price, rating, availability, loaded_at)
       │  SQL queries
       ▼
Streamlit Dashboard / log file
```

---

## 📝 Logging

Every pipeline run appends to `logs/pipeline.log`:

```
2024-11-01 14:32:01 | INFO     | scraper.scrape                | [Page  1/50] http://books.toscrape.com/...
2024-11-01 14:32:02 | INFO     | scraper.scrape                |   → collected 20 books  (running total: 20)
2024-11-01 14:34:15 | INFO     | pipeline.clean                | Loaded 1000 raw records
2024-11-01 14:34:15 | INFO     | pipeline.clean                | Validation: 0 records dropped, 1000 retained
2024-11-01 14:34:15 | INFO     | pipeline.load                 | Load complete — 'books' table now contains 1000 rows
```

---

## 🔮 Possible Extensions

- **Scheduling**: Run daily via `cron`, GitHub Actions, or Apache Airflow
- **Cloud DB**: Swap SQLite for PostgreSQL (Supabase / RDS)
- **dbt**: Add a transformation layer for more complex analytics
- **Docker**: Containerise the pipeline + dashboard
- **Alerts**: Email/Slack notification on pipeline failure
- **Unit tests**: `pytest` suite for cleaning and query functions

---

## 👤 Author
Sadeed Naeem

M.Sc. Software Engineering Student
Hochschule Heilbronn, Germany

Interests:

Data Engineering
Data Analytics
ETL Development
Cloud Technologies
Python Development

This project was developed to demonstrate practical Data Engineering skills, including data extraction, transformation, storage, SQL analytics, and dashboard development.

---

## 📄 License

MIT — free to use, adapt, and extend.
