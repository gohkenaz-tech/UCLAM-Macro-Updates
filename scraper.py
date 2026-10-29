"""
scraper.py
----------
Fetches the S&P 500 index + 11 GICS sector levels and writes them to
data/sector_data.csv.

Data source: Yahoo Finance, via the `yfinance` library. Yahoo's public
quote/chart API returns clean JSON for the S&P 500 index and each GICS
sector index, and yfinance handles the cookie/crumb handshake Yahoo
requires. This is reliable from GitHub Actions and needs no API key.

Yahoo Finance symbols (verified):
    ^GSPC       S&P 500 index
    ^SP500-10   Energy
    ^SP500-15   Materials
    ^SP500-20   Industrials
    ^SP500-25   Consumer Discretionary
    ^SP500-30   Consumer Staples
    ^SP500-35   Health Care
    ^SP500-40   Financials
    ^SP500-45   Information Technology
    ^SP500-50   Communication Services
    ^SP500-55   Utilities
    ^SP500-60   Real Estate

Runs on GitHub Actions every 24 hours. Run locally with:

    python scraper.py
"""

from __future__ import annotations

import csv
import os
import sys
import time
from datetime import datetime, timezone

import yfinance as yf

# name -> (Yahoo symbol, original MarketWatch URL kept for reference/click-through)
TARGETS = [
    {"name": "S&P 500 (Index)",        "symbol": "^GSPC",     "url": "https://www.marketwatch.com/investing/index/spx"},
    {"name": "Energy",                 "symbol": "^SP500-10", "url": "https://www.marketwatch.com/investing/index/sp500.10?countrycode=xx"},
    {"name": "Materials",              "symbol": "^SP500-15", "url": "https://www.marketwatch.com/investing/index/sp500.15?countrycode=xx"},
    {"name": "Industrials",            "symbol": "^SP500-20", "url": "https://www.marketwatch.com/investing/index/sp500.20?countrycode=xx"},
    {"name": "Consumer Discretionary", "symbol": "^SP500-25", "url": "https://www.marketwatch.com/investing/index/sp500.25?countrycode=xx"},
    {"name": "Consumer Staples",       "symbol": "^SP500-30", "url": "https://www.marketwatch.com/investing/index/sp500.30?countrycode=xx"},
    {"name": "Health Care",            "symbol": "^SP500-35", "url": "https://www.marketwatch.com/investing/index/sp500.35?countrycode=xx"},
    {"name": "Financials",             "symbol": "^SP500-40", "url": "https://www.marketwatch.com/investing/index/sp500.40?countrycode=xx"},
    {"name": "Information Technology", "symbol": "^SP500-45", "url": "https://www.marketwatch.com/investing/index/sp500.45?countrycode=xx"},
    {"name": "Communication Services", "symbol": "^SP500-50", "url": "https://www.marketwatch.com/investing/index/sp500.50?countrycode=xx"},
    {"name": "Utilities",              "symbol": "^SP500-55", "url": "https://www.marketwatch.com/investing/index/sp500.55?countrycode=xx"},
    {"name": "Real Estate",            "symbol": "^SP500-60", "url": "https://www.marketwatch.com/investing/index/sp500.60?countrycode=xx"},
]

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "sector_data.csv")

FIELDNAMES = [
    "name", "price", "change", "change_percent",
    "open", "day_low", "day_high",
    "week52_low", "week52_high", "url", "scraped_at",
]


def _round(value) -> float | None:
    try:
        if value is None:
            return None
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def scrape_one(target: dict) -> dict | None:
    symbol = target["symbol"]
    try:
        ticker = yf.Ticker(symbol)

        # 1-year daily history gives us the latest bar + the 52-week range.
        hist = ticker.history(period="1y", interval="1d", auto_adjust=False)
        if hist is None or hist.empty:
            print(f"  ! no history for {target['name']} ({symbol})", file=sys.stderr)
            return None

        last = hist.iloc[-1]
        prev_close = hist.iloc[-2]["Close"] if len(hist) >= 2 else last["Open"]

        close = _round(last["Close"])
        open_ = _round(last["Open"])
        day_low = _round(last["Low"])
        day_high = _round(last["High"])
        prev = _round(prev_close)

        change = round(close - prev, 2) if (close is not None and prev is not None) else None
        change_pct = round(change / prev * 100, 2) if (change is not None and prev) else None

        wk_low = _round(hist["Low"].min())
        wk_high = _round(hist["High"].max())
    except Exception as exc:  # noqa: BLE001 - keep one bad symbol from killing the run
        print(f"  ! error for {target['name']} ({symbol}): {exc}", file=sys.stderr)
        return None

    row = {
        "name": target["name"],
        "price": close,
        "change": change,
        "change_percent": change_pct,
        "open": open_,
        "day_low": day_low,
        "day_high": day_high,
        "week52_low": wk_low,
        "week52_high": wk_high,
        "url": target["url"],
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    if row["price"] is None and row["open"] is None:
        print(f"  ! no usable data for {target['name']}", file=sys.stderr)
        return None

    print(f"  ok {target['name']}: price={close} chg%={change_pct} 52wk={wk_low}-{wk_high}")
    return row


def main() -> int:
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"Fetching {len(TARGETS)} symbols from Yahoo Finance...")

    rows: list[dict] = []
    for target in TARGETS:
        row = scrape_one(target)
        if row:
            rows.append(row)
        time.sleep(0.4)

    if not rows:
        print("ERROR: fetched 0 rows. Keeping existing CSV if present.", file=sys.stderr)
        return 0 if os.path.exists(OUTPUT_FILE) else 1

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
