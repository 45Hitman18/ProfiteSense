"""
collect_indic_prices.py — Download real historical OHLCV data for all 96 tickers
covering the Indic-Finance article time windows (2024–2026) and compute genuine
3D and 5D future returns without any data fabrication.
"""

import sys
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
from collections import defaultdict

import yfinance as yf
import pandas as pd
import numpy as np

from database import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("collect_indic_prices")


def get_all_article_tickers() -> List[str]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT ticker FROM articles WHERE ticker IS NOT NULL AND ticker != ''")
    tickers = [r[0] for r in cur.fetchall()]
    conn.close()
    return sorted(tickers)


def fetch_and_store_historical_ohlcv(
    start_date: str = "2024-01-01",
    end_date: str = "2026-04-15",
    batch_size: int = 15
) -> int:
    """Fetch daily OHLCV for all tickers in batches and store in stock_price table."""
    tickers = get_all_article_tickers()
    # Always include benchmarks
    for idx in ["^NSEI", "^BSESN", "SPY"]:
        if idx not in tickers:
            tickers.append(idx)

    logger.info("Found %d distinct tickers to fetch prices for.", len(tickers))

    conn = get_connection()
    cur = conn.cursor()
    total_stored = 0

    # Process in batches
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        logger.info("Fetching batch %d/%d: %s", (i // batch_size) + 1, (len(tickers) + batch_size - 1) // batch_size, ", ".join(batch))

        try:
            # Download batch
            df = yf.download(
                tickers=batch,
                start=start_date,
                end=end_date,
                group_by="ticker",
                auto_adjust=False,
                threads=True,
                progress=False
            )

            if df is None or df.empty:
                logger.warning("Empty dataframe for batch: %s", batch)
                continue

            insert_rows = []

            for ticker in batch:
                try:
                    if len(batch) == 1:
                        ticker_df = df
                    else:
                        if ticker not in df.columns.levels[0]:
                            continue
                        ticker_df = df[ticker]

                    if ticker_df.empty:
                        continue

                    for dt, row in ticker_df.iterrows():
                        dt_str = dt.strftime("%Y-%m-%d")
                        close_val = row.get("Close")
                        if pd.isna(close_val):
                            continue
                        c = float(close_val.item() if hasattr(close_val, "item") else close_val)
                        if c <= 0:
                            continue

                        def _safe_float(v):
                            if pd.isna(v):
                                return None
                            return float(v.item() if hasattr(v, "item") else v)

                        o = _safe_float(row.get("Open")) or c
                        h = _safe_float(row.get("High")) or c
                        l = _safe_float(row.get("Low")) or c
                        v = _safe_float(row.get("Volume")) or 0.0
                        ac = _safe_float(row.get("Adj Close")) or c

                        insert_rows.append((ticker, dt_str, o, h, l, c, v, ac))
                except Exception as ex:
                    logger.debug("Error processing ticker %s: %s", ticker, ex)

            if insert_rows:
                cur.executemany("""
                    INSERT OR REPLACE INTO stock_price
                    (ticker, date, open, high, low, close, volume, adj_close)
                    VALUES (?,?,?,?,?,?,?,?)
                """, insert_rows)
                conn.commit()
                total_stored += len(insert_rows)
                logger.info("Stored %d price rows for batch.", len(insert_rows))

        except Exception as e:
            logger.error("Error downloading batch %s: %s", batch, e)

        time.sleep(0.5)

    conn.close()
    logger.info("Total price rows stored: %d across %d tickers.", total_stored, len(tickers))
    return total_stored


def compute_3d_5d_future_returns() -> Dict[str, Any]:
    """
    Compute genuine 3D and 5D forward returns from actual OHLCV closing prices in stock_price.
    NEVER fabricates or invents fake returns.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Load all stock prices into memory: ticker -> sorted list of (date, close)
    cur.execute("SELECT ticker, date, close FROM stock_price WHERE close > 0 ORDER BY ticker, date ASC")
    price_rows = cur.fetchall()

    prices_by_ticker = defaultdict(list)
    for t, d, c in price_rows:
        prices_by_ticker[t].append((d, float(c)))

    # Fetch articles needing 3d/5d computation
    cur.execute("""
        SELECT a.id, a.ticker, SUBSTR(a.published_at, 1, 10) as pub_date,
               a.forward_return_1d, a.forward_return_3d, a.forward_return_5d
        FROM articles a
        WHERE a.ticker IS NOT NULL AND a.published_at IS NOT NULL
    """)
    articles = cur.fetchall()

    updated_3d = 0
    updated_5d = 0
    update_data = []

    for art_id, ticker, pub_date, ret_1d, cur_3d, cur_5d in articles:
        series = prices_by_ticker.get(ticker, [])
        if not series:
            continue

        # Find entry price: on or first trading day on/after pub_date
        trading_days_after = [p for p in series if p[0] >= pub_date]
        if not trading_days_after:
            continue

        entry_date, entry_close = trading_days_after[0]
        if entry_close <= 0:
            continue

        # Look for +3 trading day close (3 trading sessions after entry)
        ret_3d = cur_3d
        if len(trading_days_after) > 3:
            day_3_date, day_3_close = trading_days_after[3]
            ret_3d = round(((day_3_close - entry_close) / entry_close) * 100, 4)
            if cur_3d is None:
                updated_3d += 1

        # Look for +5 trading day close (5 trading sessions after entry)
        ret_5d = cur_5d
        if len(trading_days_after) > 5:
            day_5_date, day_5_close = trading_days_after[5]
            ret_5d = round(((day_5_close - entry_close) / entry_close) * 100, 4)
            if cur_5d is None:
                updated_5d += 1

        if ret_3d != cur_3d or ret_5d != cur_5d:
            update_data.append((ret_3d, ret_5d, art_id))

    if update_data:
        cur.executemany("UPDATE articles SET forward_return_3d = ?, forward_return_5d = ? WHERE id = ?", update_data)
        cur.executemany("UPDATE analysis SET forward_return_3d = ?, forward_return_5d = ? WHERE article_id = ?", update_data)
        conn.commit()

    conn.close()
    logger.info("Updated %d 3D returns and %d 5D returns from actual historical prices.", updated_3d, updated_5d)
    return {
        "total_articles": len(articles),
        "updated_3d": updated_3d,
        "updated_5d": updated_5d,
        "total_records_updated": len(update_data),
    }


if __name__ == "__main__":
    print("--- 1. Fetching Historical OHLCV Prices ---")
    stored = fetch_and_store_historical_ohlcv()
    print(f"Stored {stored} price records.")
    print("--- 2. Computing Legitimate 3D and 5D Forward Returns ---")
    res = compute_3d_5d_future_returns()
    print("Computation results:", res)
