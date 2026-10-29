"""
scraper.py
----------
Fetches S&P 500 index + 11 GICS sector levels and writes them to
data/sector_data.csv.

Data source: Stooq (https://stooq.com), which serves free end-of-day index
quotes as plain CSV with no API key and no bot-blocking. This is far more
reliable for an automated, free, GitHub-hosted setup than scraping
MarketWatch (whose Akamai bot-protection blocks automated requests).

Each sector maps to an S&P 500 GICS sector index on Stooq:

    Stooq symbol   GICS sector               (MarketWatch equivalent)
    ^SPX           S&P 500 index             spx
    ^SP500-10      Energy                    sp500.10
    ^SP500-15      Materials                 sp500.15
    ^SP500-20      Industrials               sp500.20
    ^SP500-25      Consumer Discretionary    sp500.25
    ^SP500-30      Consumer Staples          sp500.30
    ^SP500-35      Health Care               sp500.35
    ^SP500-40      Financials                sp500.40
    ^SP500-45      Information Technology     sp500.45
    ^SP500-50      Communication Services    sp500.50
    ^SP500-55      Utilities                 sp500.55
    ^SP500-60      Real Estate               sp500.60

Runs on GitHub Actions every 24 hours. Run locally with:

    python scraper.py
"""

from __future__ import annotations

import csv
import io
import os
import sys
import time
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# name -> Stooq symbol. The "url" column kept in the CSV still points at the
# matching MarketWatch page so you can click through to the original source.
# ---------------------------------------------------------------------------
TARGETS = [
    {"name": "S&P 500 (Index)",        "symbol": "^SPX",      "url": "https://www.marketwatch.com/investing/index/spx"},
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

# Stooq "light" quote endpoint: returns one CSV row per symbol with
# Symbol,Date,Time,Open,High,Low,Close,Volume
QUOTE_URL = "https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"

# Stooq daily history (for the 52-week high/low): Date,Open,High,Low,Close,Volume
HISTORY_URL = "https://stooq.com/q/d/l/?s={symbol}&i=d"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "sector_data.csv")

FIELDNAMES = [
    "name", "price", "change", "change_percent",
    "open", "day_low", "day_high",
    "week52_low", "week52_high", "url", "scraped_at",
]


def _to_float(value: str) -> float | None:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _fetch_quote(symbol: str) -> dict | None:
    """Return today's OHLC quote for a symbol, or None on failure.

    DIAGNOSTIC MODE: tries several candidate symbol spellings and logs which
    one Stooq accepts, so we can lock in the correct format.
    """
    candidates = [
        symbol,                       # e.g. ^SPX
        symbol.lstrip("^"),           # e.g. SPX  / SP500-10
        symbol.lstrip("^").lower(),   # e.g. spx  / sp500-10
        symbol.lstrip("^").replace("-", ".").lower(),  # e.g. sp500.10
        symbol.lstrip("^").replace("SP500-", "^spx").lower(),
    ]
    tried = []
    for cand in dict.fromkeys(candidates):  # dedupe, keep order
        try:
            resp = requests.get(QUOTE_URL.format(symbol=cand), headers=HEADERS, timeout=30)
        except requests.RequestException as exc:
            tried.append(f"{cand}=EXC")
            continue
        body = resp.text.strip()
        ok = resp.status_code == 200 and "N/D" not in body and "Close" in body.split("\n")[0]
        has_data = ok and len(body.split("\n")) > 1 and "N/D" not in body.split("\n")[1]
        print(f"  [debug] try {cand!r}: status={resp.status_code} "
              f"first_line={body.split(chr(10))[0][:60]!r} "
              f"data_line={(body.split(chr(10))[1][:80] if len(body.split(chr(10)))>1 else '')!r}")
        if has_data:
            rows = list(csv.DictReader(io.StringIO(resp.text)))
            if rows and rows[0].get("Close") not in (None, "", "N/D"):
                print(f"  [debug] >>> WORKING symbol for {symbol} is {cand!r}")
                return rows[0]
        tried.append(cand)
    print(f"  ! no working symbol for {symbol}; tried {tried}", file=sys.stderr)
    return None
    # (unreachable legacy parse kept for reference)
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    if not rows:
        return None
    row = rows[0]
    # Stooq returns "N/D" for fields with no data.
    if row.get("Close") in (None, "", "N/D"):
        print(f"  ! no quote data for {symbol}", file=sys.stderr)
        return None
    return row


def _fetch_52week(symbol: str) -> tuple[float | None, float | None]:
    """Compute the 52-week high/low from Stooq daily history."""
    try:
        resp = requests.get(HISTORY_URL.format(symbol=symbol), headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  ! history fetch failed for {symbol}: {exc}", file=sys.stderr)
        return None, None

    rows = list(csv.DictReader(io.StringIO(resp.text)))
    # Keep roughly the last year of trading days (~252), guard short history.
    recent = rows[-252:] if len(rows) > 252 else rows
    highs = [_to_float(r.get("High")) for r in recent]
    lows = [_to_float(r.get("Low")) for r in recent]
    highs = [h for h in highs if h is not None]
    lows = [low for low in lows if low is not None]
    if not highs or not lows:
        return None, None
    return min(lows), max(highs)


def scrape_one(target: dict) -> dict | None:
    quote = _fetch_quote(target["symbol"])
    if not quote:
        return None

    close = _to_float(quote.get("Close"))
    open_ = _to_float(quote.get("Open"))
    high = _to_float(quote.get("High"))
    low = _to_float(quote.get("Low"))

    change = round(close - open_, 2) if (close is not None and open_ is not None) else None
    change_pct = round(change / open_ * 100, 2) if (change is not None and open_) else None

    wk_low, wk_high = _fetch_52week(target["symbol"])

    row = {
        "name": target["name"],
        "price": close,
        "change": change,
        "change_percent": change_pct,
        "open": open_,
        "day_low": low,
        "day_high": high,
        "week52_low": wk_low,
        "week52_high": wk_high,
        "url": target["url"],
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    if row["price"] is None and row["open"] is None:
        print(f"  ! no usable data for {target['name']}", file=sys.stderr)
        return None

    print(f"  ok {target['name']}: price={row['price']} 52wk={wk_low}-{wk_high}")
    return row


def main() -> int:
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"Fetching {len(TARGETS)} symbols from Stooq...")

    rows: list[dict] = []
    for target in TARGETS:
        row = scrape_one(target)
        if row:
            rows.append(row)
        time.sleep(0.5)  # be polite to the server

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
