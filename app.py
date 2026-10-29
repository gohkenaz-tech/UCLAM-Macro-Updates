"""
app.py
------
Streamlit dashboard for S&P 500 index + sector data.

Reads data/sector_data.csv (produced by scraper.py) and displays it with
interactive charts and a table. Run locally with:

    streamlit run app.py
"""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sector_data.csv")

st.set_page_config(
    page_title="S&P 500 Sector Dashboard",
    page_icon="📈",
    layout="wide",
)


@st.cache_data(ttl=600)  # re-read the file at most every 10 minutes
def load_data() -> pd.DataFrame:
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame()
    df = pd.read_csv(DATA_FILE)
    numeric_cols = [
        "price", "change", "change_percent", "open",
        "day_low", "day_high", "week52_low", "week52_high",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


df = load_data()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("📈 S&P 500 Sector Dashboard")
st.caption("Index and 11 GICS sector levels, sourced daily from MarketWatch.")

if df.empty:
    st.warning(
        "No data found yet. Run `python scraper.py` to fetch data, "
        "or wait for the scheduled GitHub Action to run."
    )
    st.stop()

# Last updated timestamp
if "scraped_at" in df.columns and df["scraped_at"].notna().any():
    try:
        last = pd.to_datetime(df["scraped_at"]).max()
        st.caption(f"🕒 Data last updated: **{last.strftime('%Y-%m-%d %H:%M UTC')}**")
    except Exception:
        pass

# Split the index row from the sector rows.
index_mask = df["name"].str.contains("Index", case=False, na=False)
index_row = df[index_mask]
sectors = df[~index_mask].copy()

# ---------------------------------------------------------------------------
# Top metrics: the headline index
# ---------------------------------------------------------------------------
if not index_row.empty:
    r = index_row.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("S&P 500", f"{r['price']:,.2f}" if pd.notna(r["price"]) else "—",
              f"{r['change']:+.2f} ({r['change_percent']:+.2f}%)"
              if pd.notna(r["change"]) else None)
    c2.metric("Open", f"{r['open']:,.2f}" if pd.notna(r["open"]) else "—")
    c3.metric("Day Range",
              f"{r['day_low']:,.2f} – {r['day_high']:,.2f}"
              if pd.notna(r["day_low"]) else "—")
    c4.metric("52-Week Range",
              f"{r['week52_low']:,.2f} – {r['week52_high']:,.2f}"
              if pd.notna(r["week52_low"]) else "—")

st.divider()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.header("Filters")
all_sectors = sorted(sectors["name"].dropna().unique().tolist())
chosen = st.sidebar.multiselect("Sectors to show", all_sectors, default=all_sectors)
view = sectors[sectors["name"].isin(chosen)] if chosen else sectors

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
left, right = st.columns(2)

with left:
    st.subheader("Daily % Change by Sector")
    if "change_percent" in view.columns and view["change_percent"].notna().any():
        chart_df = view.dropna(subset=["change_percent"]).sort_values("change_percent")
        fig = px.bar(
            chart_df, x="change_percent", y="name", orientation="h",
            color="change_percent", color_continuous_scale=["#d62728", "#dddddd", "#2ca02c"],
            color_continuous_midpoint=0, labels={"change_percent": "% change", "name": ""},
        )
        fig.update_layout(height=430, coloraxis_showscale=False, margin=dict(l=0, r=10, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No % change data available.")

with right:
    st.subheader("Current Price Level by Sector")
    if "price" in view.columns and view["price"].notna().any():
        price_df = view.dropna(subset=["price"]).sort_values("price", ascending=True)
        fig2 = px.bar(
            price_df, x="price", y="name", orientation="h",
            labels={"price": "Price", "name": ""}, color_discrete_sequence=["#1f77b4"],
        )
        fig2.update_layout(height=430, margin=dict(l=0, r=10, t=10, b=0))
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No price data available.")

# ---------------------------------------------------------------------------
# 52-week position gauge: how far each sector sits within its yearly range
# ---------------------------------------------------------------------------
st.subheader("Position Within 52-Week Range")
pos = view.dropna(subset=["price", "week52_low", "week52_high"]).copy()
if not pos.empty:
    span = (pos["week52_high"] - pos["week52_low"]).replace(0, pd.NA)
    pos["pct_of_range"] = ((pos["price"] - pos["week52_low"]) / span * 100).round(1)
    pos = pos.sort_values("pct_of_range")
    fig3 = px.bar(
        pos, x="pct_of_range", y="name", orientation="h",
        range_x=[0, 100], labels={"pct_of_range": "% of 52-week range", "name": ""},
        color="pct_of_range", color_continuous_scale="Blues",
    )
    fig3.update_layout(height=430, coloraxis_showscale=False, margin=dict(l=0, r=10, t=10, b=0))
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("Not enough range data to compute positions.")

# ---------------------------------------------------------------------------
# Data table
# ---------------------------------------------------------------------------
st.subheader("All Data")
display = view.rename(columns={
    "name": "Sector", "price": "Price", "change": "Change",
    "change_percent": "% Change", "open": "Open",
    "day_low": "Day Low", "day_high": "Day High",
    "week52_low": "52wk Low", "week52_high": "52wk High",
})
cols = ["Sector", "Price", "Change", "% Change", "Open",
        "Day Low", "Day High", "52wk Low", "52wk High"]
st.dataframe(display[[c for c in cols if c in display.columns]],
             use_container_width=True, hide_index=True)

st.download_button(
    "⬇️ Download data as CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="sp500_sector_data.csv",
    mime="text/csv",
)
