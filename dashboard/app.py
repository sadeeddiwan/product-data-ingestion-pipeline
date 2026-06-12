"""
dashboard/app.py
================
Streamlit dashboard for the Product Data Ingestion Pipeline.

Displays:
  • KPI metrics   — total books, avg price, in-stock %, top rating
  • Bar chart     — books per star rating
  • Donut chart   — availability breakdown
  • Bar chart     — avg price per rating
  • Histogram     — price-band distribution
  • Heatmap table — rating × availability × avg price
  • Top-10 table  — most expensive books
  • Data browser  — filterable, searchable, downloadable full dataset

Run locally:
    streamlit run dashboard/app.py

Streamlit Community Cloud:
    Set Main file path → dashboard/app.py
"""

import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── Path resolution (works wherever streamlit is invoked from) ────────────────
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from config import DB_PATH, LOG_PATH, DB_TABLE

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Product Pipeline Dashboard",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help":    "https://github.com/your-username/product-pipeline",
        "Report a bug":"https://github.com/your-username/product-pipeline/issues",
        "About":       "**Product Data Ingestion Pipeline** — DE Portfolio Project",
    },
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* KPI cards */
    div[data-testid="metric-container"] {
        background:    #1e2130;
        border-radius: 12px;
        padding:       0.9rem 1.2rem;
        border-left:   4px solid #4f8bf9;
        box-shadow:    0 2px 8px rgba(0,0,0,0.3);
    }
    div[data-testid="metric-container"] > label {
        font-size: 0.78rem !important;
        color: #9ca3af !important;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    div[data-testid="metric-container"] > div {
        font-size: 1.7rem !important;
        font-weight: 700 !important;
        color: #f9fafb !important;
    }
    /* Section headers */
    .section-label {
        font-size: 0.72rem;
        font-weight: 600;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.25rem;
    }
    /* Badge pills */
    .badge-green { background:#14532d; color:#86efac; padding:2px 8px;
                   border-radius:12px; font-size:0.78rem; font-weight:600; }
    .badge-red   { background:#450a0a; color:#fca5a5; padding:2px 8px;
                   border-radius:12px; font-size:0.78rem; font-weight:600; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Plotly shared theme ───────────────────────────────────────────────────────
PLOT_BG   = "rgba(0,0,0,0)"
GRID_CLR  = "#2d3748"
FONT_CLR  = "#e2e8f0"
PALETTE   = px.colors.sequential.Blues
BASE_LAYOUT = dict(
    plot_bgcolor  = PLOT_BG,
    paper_bgcolor = PLOT_BG,
    font          = dict(color=FONT_CLR),
    margin        = dict(t=30, b=10, l=10, r=10),
    xaxis         = dict(gridcolor=GRID_CLR, showgrid=True),
    yaxis         = dict(gridcolor=GRID_CLR, showgrid=True),
)


# ── Data access layer (cached) ────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _load_books() -> pd.DataFrame:
    """Return all books from SQLite as a DataFrame."""
    conn = sqlite3.connect(str(DB_PATH))
    df   = pd.read_sql(f"SELECT * FROM {DB_TABLE} ORDER BY price DESC;", conn)
    conn.close()
    return df


@st.cache_data(ttl=300, show_spinner=False)
def _load_kpis() -> dict:
    """Pre-compute all KPI values in a single DB round-trip."""
    conn = sqlite3.connect(str(DB_PATH))
    cur  = conn.cursor()

    kpis = {
        "total":       cur.execute(f"SELECT COUNT(*) FROM {DB_TABLE}").fetchone()[0],
        "avg_price":   cur.execute(f"SELECT ROUND(AVG(price),2) FROM {DB_TABLE}").fetchone()[0],
        "in_stock_pct":cur.execute(
            f"""SELECT ROUND(100.0*SUM(CASE WHEN availability='In Stock' THEN 1 ELSE 0 END)
                /COUNT(*),1) FROM {DB_TABLE}"""
        ).fetchone()[0],
        "top_rating":  cur.execute(
            f"SELECT rating FROM {DB_TABLE} GROUP BY rating ORDER BY COUNT(*) DESC LIMIT 1"
        ).fetchone()[0],
        "max_price":   cur.execute(f"SELECT MAX(price) FROM {DB_TABLE}").fetchone()[0],
        "min_price":   cur.execute(f"SELECT MIN(price) FROM {DB_TABLE}").fetchone()[0],
    }
    conn.close()
    return kpis


@st.cache_data(ttl=300, show_spinner=False)
def _load_by_rating() -> pd.DataFrame:
    conn = sqlite3.connect(str(DB_PATH))
    df   = pd.read_sql(
        f"""SELECT rating,
                   COUNT(*)             AS count,
                   ROUND(AVG(price),2)  AS avg_price,
                   ROUND(MIN(price),2)  AS min_price,
                   ROUND(MAX(price),2)  AS max_price
            FROM {DB_TABLE}
            GROUP BY rating
            ORDER BY rating;""",
        conn,
    )
    conn.close()
    return df


@st.cache_data(ttl=300, show_spinner=False)
def _load_availability() -> pd.DataFrame:
    conn = sqlite3.connect(str(DB_PATH))
    df   = pd.read_sql(
        f"""SELECT availability,
                   COUNT(*)                                            AS count,
                   ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (), 1)     AS pct
            FROM {DB_TABLE}
            GROUP BY availability;""",
        conn,
    )
    conn.close()
    return df


@st.cache_data(ttl=300, show_spinner=False)
def _load_top10() -> pd.DataFrame:
    conn = sqlite3.connect(str(DB_PATH))
    df   = pd.read_sql(
        f"""SELECT title, price, rating, availability
            FROM {DB_TABLE} ORDER BY price DESC LIMIT 10;""",
        conn,
    )
    conn.close()
    return df


@st.cache_data(ttl=300, show_spinner=False)
def _load_price_bands() -> pd.DataFrame:
    conn = sqlite3.connect(str(DB_PATH))
    df   = pd.read_sql(
        f"""SELECT
              CASE
                WHEN price <  10 THEN '£0–10'
                WHEN price <  20 THEN '£10–20'
                WHEN price <  30 THEN '£20–30'
                WHEN price <  40 THEN '£30–40'
                WHEN price <  50 THEN '£40–50'
                ELSE                   '£50+'
              END         AS band,
              COUNT(*)    AS count,
              MIN(price)  AS _sort
            FROM {DB_TABLE}
            GROUP BY band
            ORDER BY _sort;""",
        conn,
    )
    conn.close()
    return df.drop(columns=["_sort"])


def _db_ready() -> bool:
    return DB_PATH.exists() and DB_PATH.stat().st_size > 1_000


# ── Pipeline runner ───────────────────────────────────────────────────────────

def _run_pipeline() -> int:
    """Spawn main.py as a subprocess and stream its output into Streamlit."""
    log_box = st.empty()
    lines   = []

    proc = subprocess.Popen(
        [sys.executable, str(ROOT_DIR / "main.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=str(ROOT_DIR),
    )

    for line in proc.stdout:
        lines.append(line.rstrip())
        log_box.code("\n".join(lines[-40:]), language="bash")

    proc.wait()
    return proc.returncode


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📦 Pipeline Control")
    st.markdown("---")

    # ── Meta info ─────────────────────────────────────────────────────────────
    col_a, col_b = st.columns(2)
    col_a.markdown("**Source**")
    col_a.caption("books.toscrape.com")
    col_b.markdown("**Store**")
    col_b.caption("SQLite · books.db")

    if _db_ready():
        mtime = datetime.fromtimestamp(DB_PATH.stat().st_mtime)
        st.caption(f"🕐 Last loaded: **{mtime.strftime('%Y-%m-%d %H:%M')}**")
    else:
        st.caption("❌ Database not found")

    st.markdown("---")

    # ── Action buttons ────────────────────────────────────────────────────────
    if st.button("🚀  Run Full Pipeline", type="primary", use_container_width=True):
        with st.spinner("Running pipeline — this takes ~2 minutes …"):
            rc = _run_pipeline()
        if rc == 0:
            st.success("✅ Pipeline complete!")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("❌ Pipeline failed. See log output above.")

    if _db_ready() and st.button("🔄  Refresh Dashboard", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")

    # ── Filters (only shown when data exists) ─────────────────────────────────
    if _db_ready():
        st.markdown("### 🔎 Filters")

        rating_sel = st.multiselect(
            "Star Rating",
            options=[1, 2, 3, 4, 5],
            default=[1, 2, 3, 4, 5],
            format_func=lambda r: "⭐" * r,
        )

        avail_sel = st.radio(
            "Availability",
            options=["All", "In Stock", "Out of Stock"],
            index=0,
            horizontal=True,
        )

        price_sel = st.slider(
            "Price (£)",
            min_value=0.0,
            max_value=60.0,
            value=(0.0, 60.0),
            step=0.5,
        )

    st.markdown("---")
    st.markdown(
        "<div style='font-size:0.72rem;color:#4b5563;text-align:center'>"
        "Product Data Ingestion Pipeline<br>DE Portfolio Project</div>",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT
# ══════════════════════════════════════════════════════════════════════════════

st.markdown(
    "# 📦 Product Data Ingestion Pipeline"
)
st.markdown(
    "End-to-end ETL: **Web Scraping → Cleaning & Validation → SQLite → SQL Analytics → Dashboard**"
)
st.markdown("---")

# ── Empty state ───────────────────────────────────────────────────────────────
if not _db_ready():
    st.warning("⚠️  No data found. Click **Run Full Pipeline** in the sidebar.")
    with st.expander("ℹ️  What will happen?"):
        st.markdown(
            """
| Step | Action | Output |
|------|--------|--------|
| 1 | Scrape 1 000 books from books.toscrape.com | `data/raw/books_raw.csv` |
| 2 | Clean & validate (price, rating, availability) | `data/processed/books_clean.csv` |
| 3 | Load into SQLite | `data/db/books.db` |
| 4 | Execute SQL analytics | Logged + displayed here |

Estimated time: **~2 minutes** (network-bound).
            """
        )
    st.stop()

# ── Load data ─────────────────────────────────────────────────────────────────
with st.spinner("Loading data …"):
    kpis      = _load_kpis()
    df_all    = _load_books()
    by_rating = _load_by_rating()
    avail_df  = _load_availability()
    top10     = _load_top10()
    bands_df  = _load_price_bands()

# ── Apply sidebar filters to the browse table ─────────────────────────────────
df_filt = df_all.copy()
df_filt = df_filt[df_filt["rating"].isin(rating_sel)]
df_filt = df_filt[df_filt["price"].between(price_sel[0], price_sel[1])]
if avail_sel != "All":
    df_filt = df_filt[df_filt["availability"] == avail_sel]


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — KPI METRICS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### 📊 Key Metrics")
m1, m2, m3, m4 = st.columns(4)

m1.metric(
    label="📚  Total Products",
    value=f"{kpis['total']:,}",
)
m2.metric(
    label="💰  Average Price",
    value=f"£{kpis['avg_price']:.2f}",
    help=f"Range: £{kpis['min_price']:.2f} – £{kpis['max_price']:.2f}",
)
m3.metric(
    label="✅  In Stock",
    value=f"{kpis['in_stock_pct']}%",
    delta=f"{kpis['in_stock_pct'] - 50:.1f}% vs 50% baseline",
    delta_color="normal",
)
m4.metric(
    label="⭐  Most Common Rating",
    value=f"{'⭐' * kpis['top_rating']}",
    help=f"Rating {kpis['top_rating']} out of 5",
)

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — RATING & AVAILABILITY CHARTS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### 📈 Distribution Analysis")

chart_l, chart_r = st.columns(2)

# ── Books by rating (bar) ─────────────────────────────────────────────────────
with chart_l:
    st.markdown("**Books per Star Rating**")
    by_rating_display = by_rating.copy()
    by_rating_display["label"] = by_rating_display["rating"].apply(
        lambda r: "⭐" * r
    )
    fig_rating = px.bar(
        by_rating_display,
        x="rating",
        y="count",
        color="count",
        color_continuous_scale="Blues",
        text="count",
        labels={"label": "Rating", "count": "Books"},
    )
    fig_rating.update_traces(textposition="outside", textfont_size=13)
    fig_rating.update_layout(
        **BASE_LAYOUT,
        coloraxis_showscale=False,
        showlegend=False,
        yaxis_title="Number of Books",
        xaxis_title="Star Rating",
    )
    st.plotly_chart(fig_rating, use_container_width=True)

with chart_r:
    st.markdown("**Price vs Rating Relationship**")

    # Correlation calculation
    corr = round(
        df_all["price"].corr(df_all["rating"]),
        3
    )

    fig_scatter = px.scatter(
        df_all,
        x="rating",
        y="price",
        color="rating",
        opacity=0.75,
        color_discrete_sequence=px.colors.sequential.Blues_r,
        hover_data={
            "title": True,
            "price": ":.2f",
            "rating": True,
        },
    )

    fig_scatter.update_traces(
        marker=dict(
            size=9,
            line=dict(
                width=0.5,
                color="white"
            )
        )
    )

    fig_scatter.update_layout(
        **{
            k: v
            for k, v in BASE_LAYOUT.items()
            if k not in ("xaxis", "yaxis")
        },
        xaxis=dict(
            title="Star Rating",
            tickmode="array",
            tickvals=[1, 2, 3, 4, 5],
            gridcolor=GRID_CLR,
        ),
        yaxis=dict(
            title="Price (£)",
            gridcolor=GRID_CLR,
        ),
        showlegend=False,
        height=450,
    )

    st.plotly_chart(
        fig_scatter,
        use_container_width=True
    )

    # Insight card
    if abs(corr) < 0.2:
        insight = "Very weak relationship"
    elif abs(corr) < 0.5:
        insight = "Moderate relationship"
    else:
        insight = "Strong relationship"

    st.info(
        f"📈 Price–Rating Correlation: **{corr}** ({insight})"
    )

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — PRICE ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### 💷 Price Analysis")

p_col1, p_col2 = st.columns(2)

# ── Avg price by rating ───────────────────────────────────────────────────────
with p_col1:
    st.markdown("**Average Price by Star Rating**")
    fig_avg = px.bar(
        by_rating,
        x="rating",
        y="avg_price",
        color="avg_price",
        color_continuous_scale="Oranges",
        text="avg_price",
        labels={"rating": "Star Rating", "avg_price": "Avg Price (£)"},
    )
    fig_avg.update_traces(
        texttemplate="£%{text:.2f}",
        textposition="outside",
        textfont_size=12,
    )
    fig_avg.update_layout(
    **{k: v for k, v in BASE_LAYOUT.items() if k != "xaxis"},
    coloraxis_showscale=False,
    yaxis_title="Average Price (£)",
    xaxis=dict(
        tickmode="array",
        tickvals=[1, 2, 3, 4, 5],
        gridcolor=GRID_CLR,
    ),
)
    st.plotly_chart(fig_avg, use_container_width=True)

# ── Price band histogram ──────────────────────────────────────────────────────
with p_col2:
    st.markdown("**Price Distribution (£10 bands)**")
    fig_bands = px.bar(
        bands_df,
        x="band",
        y="count",
        color="count",
        color_continuous_scale="Purples",
        text="count",
        labels={"band": "Price Band", "count": "Books"},
    )
    fig_bands.update_traces(textposition="outside", textfont_size=12)
    fig_bands.update_layout(
        **BASE_LAYOUT,
        coloraxis_showscale=False,
        yaxis_title="Number of Books",
        xaxis_title="Price Range (£)",
    )
    st.plotly_chart(fig_bands, use_container_width=True)

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — PRICE RANGE PER RATING (min/avg/max)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### 📉 Price Range per Rating")

fig_range = go.Figure()
fig_range.add_trace(go.Bar(
    x=by_rating["rating"],
    y=by_rating["avg_price"],
    name="Avg Price",
    marker_color="#60a5fa",
    text=by_rating["avg_price"].apply(lambda v: f"£{v:.2f}"),
    textposition="outside",
))
fig_range.add_trace(go.Scatter(
    x=by_rating["rating"],
    y=by_rating["max_price"],
    mode="markers+lines",
    name="Max Price",
    marker=dict(color="#f97316", size=9, symbol="triangle-up"),
    line=dict(color="#f97316", dash="dot", width=1.5),
))
fig_range.add_trace(go.Scatter(
    x=by_rating["rating"],
    y=by_rating["min_price"],
    mode="markers+lines",
    name="Min Price",
    marker=dict(color="#34d399", size=9, symbol="triangle-down"),
    line=dict(color="#34d399", dash="dot", width=1.5),
))
fig_range.update_layout(
    **{
        k: v
        for k, v in BASE_LAYOUT.items()
        if k not in ["xaxis", "yaxis"]
    },
    xaxis=dict(
        title="Star Rating",
        gridcolor=GRID_CLR,
    ),
    yaxis=dict(
        title="Price (£)",
        gridcolor=GRID_CLR,
    ),
)
st.plotly_chart(fig_range, use_container_width=True)

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — TOP 10 MOST EXPENSIVE BOOKS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### 🏆 Top 10 Most Expensive Books")

top10_display = top10.copy()
top10_display["rank"]         = range(1, 11)
top10_display["price_fmt"]    = top10_display["price"].apply(lambda p: f"£{p:.2f}")
top10_display["rating_stars"] = top10_display["rating"].apply(lambda r: "⭐" * int(r))
top10_display["avail_badge"]  = top10_display["availability"].apply(
    lambda a: "✅ In Stock" if a == "In Stock" else "❌ Out of Stock"
)

st.dataframe(
    top10_display[["rank", "title", "price_fmt", "rating_stars", "avail_badge"]].rename(
        columns={
            "rank":         "#",
            "title":        "Book Title",
            "price_fmt":    "Price",
            "rating_stars": "Rating",
            "avail_badge":  "Availability",
        }
    ),
    use_container_width=True,
    height=395,
    hide_index=True,
)

# Horizontal bar chart of top-10
fig_top10 = px.bar(
    top10.iloc[::-1],   # reverse so highest is at top
    x="price",
    y="title",
    orientation="h",
    color="price",
    color_continuous_scale="Reds",
    text="price",
    labels={"price": "Price (£)", "title": ""},
)
fig_top10.update_traces(
    texttemplate="£%{text:.2f}",
    textposition="outside",
    textfont_size=11,
)
fig_top10.update_layout(
    **{k: v for k, v in BASE_LAYOUT.items() if k != "margin"},
    coloraxis_showscale=False,
    height=420,
    margin=dict(l=220, t=20, b=20, r=60),
)
st.plotly_chart(fig_top10, use_container_width=True)

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — DATA BROWSER (filtered)
# ══════════════════════════════════════════════════════════════════════════════
with st.expander(
    f"🔍  Browse Dataset  —  {len(df_filt):,} books match current filters",
    expanded=False,
):
    # Free-text search
    query = st.text_input("Search by title", placeholder="e.g. Python, History …")
    if query:
        df_filt = df_filt[df_filt["title"].str.contains(query, case=False, na=False)]

    # Display
    browse_df = df_filt[["title", "price", "rating", "availability"]].copy()
    browse_df["price"]  = browse_df["price"].apply(lambda p: f"£{p:.2f}")
    browse_df["rating"] = browse_df["rating"].apply(lambda r: "⭐" * int(r))
    browse_df = browse_df.rename(
        columns={
            "title":        "Book Title",
            "price":        "Price",
            "rating":       "Rating",
            "availability": "Availability",
        }
    )

    st.dataframe(browse_df, use_container_width=True, height=400, hide_index=True)

    # CSV download
    csv_bytes = df_filt[["title", "price", "rating", "availability"]] \
                    .to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️  Download Filtered Dataset as CSV",
        data=csv_bytes,
        file_name="books_filtered.csv",
        mime="text/csv",
    )

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(
    """
    <div style="text-align:center; color:#4b5563; font-size:0.82rem; padding:1.5rem 0 0.5rem;">
        🔧  Built with &nbsp;
        <strong>Python · Requests · BeautifulSoup4 · Pandas · SQLite · Streamlit · Plotly</strong>
        <br><br>
        <a href="https://github.com/your-username/product-pipeline"
           style="color:#60a5fa; text-decoration:none;">
            📁 View source on GitHub
        </a>
    </div>
    """,
    unsafe_allow_html=True,
)
