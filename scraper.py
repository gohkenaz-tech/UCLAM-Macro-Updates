"""
scraper.py
----------
Fetches S&P 500 index + sector data from MarketWatch and writes it to
data/sector_data.csv.

This script is meant to run on GitHub Actions (which has full internet
access) every 24 hours. It can also be run locally:

    python scraper.py

MarketWatch blocks obvious bots, so we send browser-like headers. If a
page can't be fetched or parsed, that row is skipped (with a warning)
rather than crashing the whole run, so the dashboard always has data.
"""

from __future__ import annotations

import csv
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# The 12 MarketWatch pages. "name" is a friendly label shown in the dashboard.
# The sp500.XX codes are GICS sector codes.
# ---------------------------------------------------------------------------
TARGETS = [
    {"name": "S&P 500 (Index)",        "url": "https://www.marketwatch.com/investing/index/spx"},
    {"name": "Energy",                 "url": "https://www.marketwatch.com/investing/index/sp500.10?countrycode=xx"},
    {"name": "Materials",              "url": "https://www.marketwatch.com/investing/index/sp500.15?countrycode=xx"},
    {"name": "Industrials",            "url": "https://www.marketwatch.com/investing/index/sp500.20?countrycode=xx"},
    {"name": "Consumer Discretionary", "url": "https://www.marketwatch.com/investing/index/sp500.25?countrycode=xx"},
    {"name": "Consumer Staples",       "url": "https://www.marketwatch.com/investing/index/sp500.30?countrycode=xx"},
    {"name": "Health Care",            "url": "https://www.marketwatch.com/investing/index/sp500.35?countrycode=xx"},
    {"name": "Financials",             "url": "https://www.marketwatch.com/investing/index/sp500.40?countrycode=xx"},
    {"name": "Information Technology", "url": "https://www.marketwatch.com/investing/index/sp500.45?countrycode=xx"},
    {"name": "Communication Services", "url": "https://www.marketwatch.com/investing/index/sp500.50?countrycode=xx"},
    {"name": "Utilities",              "url": "https://www.marketwatch.com/investing/index/sp500.55?countrycode=xx"},
    {"name": "Real Estate",            "url": "https://www.marketwatch.com/investing/index/sp500.60?countrycode=xx"},
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.marketwatch.com/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "sector_data.csv")

# Column order written to the CSV.
FIELDNAMES = [
    "name", "price", "change", "change_percent",
    "open", "day_low", "day_high",
    "week52_low", "week52_high", "url", "scraped_at",
]


def _clean_number(text: str) -> float | None:
    """Turn a string like '1,234.56%' or '-0.42' into a float, or None."""
    if text is None:
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", text.replace(",", ""))
    if cleaned in ("", "-", ".", "-."):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _get_key_data(soup: BeautifulSoup) -> dict[str, str]:
    """
    MarketWatch renders a 'Key Data' list where each item has a label
    (e.g. 'Open') and a value. We collect them into a {label: value} dict.
    """
    result: dict[str, str] = {}
    for li in soup.select("ul.list--kv li.kv__item, li.kv__item"):
        label_el = li.select_one(".label, .kv__label")
        value_el = li.select_one(".primary, .kv__value, .kv__primary")
        if label_el and value_el:
            result[label_el.get_text(strip=True)] = value_el.get_text(strip=True)
    return result


def _split_range(value: str) -> tuple[float | None, float | None]:
    """Split a '703.80 - 899.94' style range into (low, high)."""
    if not value:
        return None, None
    parts = re.split(r"\s*-\s*", value)
    if len(parts) == 2:
        return _clean_number(parts[0]), _clean_number(parts[1])
    return None, None


def scrape_one(target: dict) -> dict | None:
    """Fetch and parse a single MarketWatch page. Returns a row dict or None."""
    try:
        resp = requests.get(target["url"], headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  ! Failed to fetch {target['name']}: {exc}", file=sys.stderr)
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    # Current price + change usually live in the quote header.
    price_el = soup.select_one(".intraday__price .value, bg-quote.value, .intraday__price bg-quote")
    change_el = soup.select_one(".intraday__change .change--point--q bg-quote, .change--point--q")
    pct_el = soup.select_one(".intraday__change .change--percent--q bg-quote, .change--percent--q")

    kv = _get_key_data(soup)
    day_low, day_high = _split_range(kv.get("Day Range", ""))
    wk_low, wk_high = _split_range(kv.get("52 Week Range", ""))

    row = {
        "name": target["name"],
        "price": _clean_number(price_el.get_text(strip=True)) if price_el else None,
        "change": _clean_number(change_el.get_text(strip=True)) if change_el else None,
        "change_percent": _clean_number(pct_el.get_text(strip=True)) if pct_el else None,
        "open": _clean_number(kv.get("Open")),
        "day_low": day_low,
        "day_high": day_high,
        "week52_low": wk_low,
        "week52_high": wk_high,
        "url": target["url"],
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    if row["price"] is None and row["open"] is None:
        print(f"  ! Parsed no usable data for {target['name']}", file=sys.stderr)
        return None

    print(f"  ok {target['name']}: price={row['price']} open={row['open']}")
    return row


def main() -> int:
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"Scraping {len(TARGETS)} MarketWatch pages...")

    rows: list[dict] = []
    for target in TARGETS:
        row = scrape_one(target)
        if row:
            rows.append(row)
        time.sleep(1.5)  # be polite; avoid hammering the server

    if not rows:
        print("ERROR: scraped 0 rows. Keeping existing CSV if present.", file=sys.stderr)
        # Exit non-zero only if there is no existing data to fall back on.
        return 0 if os.path.exists(OUTPUT_FILE) else 1

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
