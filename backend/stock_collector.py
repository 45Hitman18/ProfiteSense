"""
stock_collector.py — Fetch and store OHLCV historical data via yfinance.
Called during /api/ml/collect-prices or on demand.
Covers BOTH recent 90-day data AND the historical period of articles in the DB
so the ML labeling pipeline can match articles to actual future price returns.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

logger = logging.getLogger("stock_collector")

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False

from database import get_connection

# Default period to fetch (recent data)
DEFAULT_PERIOD_DAYS = 90


def get_tracked_tickers() -> List[str]:
    """Get all unique tickers that have analysis rows."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT ticker FROM analysis WHERE ticker IS NOT NULL AND ticker != ''"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]


def _get_article_date_range() -> tuple:
    """Return (earliest_article_date, latest_article_date) from the articles table."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT a.published_at
        FROM articles a
        JOIN analysis an ON a.id = an.article_id
        WHERE an.ticker IS NOT NULL AND a.published_at IS NOT NULL
          AND length(a.published_at) >= 8
    """).fetchall()
    conn.close()

    dates = []
    for r in rows:
        raw = str(r[0])
        # Handle formats: '2024-04-23T08:08:59', '20261001T112705', '2024-04-23', '20261001'
        try:
            if 'T' in raw:
                d = raw.split('T')[0]
            else:
                d = raw[:10]
            # Handle compact format '20261001' -> '2026-10-01'
            if len(d) == 8 and '-' not in d:
                d = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
            if len(d) == 10:
                dates.append(d)
        except Exception:
            continue

    if not dates:
        return None, None
    return min(dates), max(dates)


def _fetch_ticker(ticker: str, start: str, end: str, conn) -> int:
    """Fetch and store price data for one ticker. Returns number of rows stored."""
    try:
        data = yf.download(ticker, start=start, end=end,
                           auto_adjust=True, progress=False, threads=False)
        if data.empty:
            logger.warning("No data for %s (%s to %s)", ticker, start, end)
            return 0

        count = 0
        for date, row in data.iterrows():
            date_str = date.strftime("%Y-%m-%d")

            def _get(col):
                try:
                    val = row[col]
                    if hasattr(val, 'item'):
                        return float(val.item())
                    return float(val)
                except Exception:
                    return None

            conn.execute("""
                INSERT OR REPLACE INTO stock_price
                (ticker, date, open, high, low, close, volume, adj_close)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                ticker, date_str,
                _get("Open"), _get("High"), _get("Low"),
                _get("Close"), _get("Volume"), _get("Close"),
            ))
            count += 1

        logger.info("Stored %d price rows for %s", count, ticker)
        return count
    except Exception as e:
        logger.error("Price fetch failed for %s: %s", ticker, e)
        return 0


def fetch_and_store_prices(tickers: list = None, period_days: int = DEFAULT_PERIOD_DAYS) -> dict:
    """
    Download OHLCV from yfinance for all tracked tickers.

    Fetches TWO windows:
    1. Recent 90-day window (for current/future labeling)
    2. Historical window matching article publication dates (for retrospective labeling)

    This ensures the ML pipeline can always find 'future' prices relative to
    any article in the database.
    """
    if not HAS_YF:
        return {"error": "yfinance not installed"}

    if tickers is None:
        tickers = get_tracked_tickers()

    if not tickers:
        return {"stored_rows": 0, "tickers": [], "message": "No tickers with analysis data found."}

    # Window 1: recent 90 days through tomorrow (for future labels on recent articles)
    recent_start = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")
    recent_end   = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")

    # Window 2: historical — cover the article date range + 10 extra days for future returns
    article_min, article_max = _get_article_date_range()
    fetch_windows = [(recent_start, recent_end, "recent")]

    if article_min:
        # Parse and extend: start 5 days before earliest article, end 10 days after latest
        try:
            art_start_dt = datetime.strptime(article_min, "%Y-%m-%d") - timedelta(days=5)
            art_end_dt   = datetime.strptime(article_max, "%Y-%m-%d") + timedelta(days=10)
            hist_start   = art_start_dt.strftime("%Y-%m-%d")
            hist_end     = art_end_dt.strftime("%Y-%m-%d")
            # Only add historical window if it doesn't overlap with recent (gap > 30 days)
            if hist_end < recent_start:
                fetch_windows.append((hist_start, hist_end, "historical"))
                logger.info("Adding historical price window: %s to %s", hist_start, hist_end)
            else:
                # Merge: start from historical, end at tomorrow
                fetch_windows = [(hist_start, recent_end, "combined")]
                logger.info("Combined price window: %s to %s", hist_start, recent_end)
        except Exception as e:
            logger.warning("Failed to compute historical window: %s", e)

    # Always include market indices
    index_tickers = ["^NSEI", "SPY", "^BSESN"]
    all_tickers = list(set(tickers + index_tickers))

    conn = get_connection()
    total_rows = 0
    failed = []
    date_ranges_fetched = []

    for (start, end, window_label) in fetch_windows:
        logger.info("Fetching %s window: %s to %s (%d tickers)", window_label, start, end, len(all_tickers))
        date_ranges_fetched.append(f"{start} to {end} [{window_label}]")
        for ticker in all_tickers:
            rows = _fetch_ticker(ticker, start, end, conn)
            if rows == 0 and ticker not in index_tickers:
                failed.append(f"{ticker}({window_label})")
            total_rows += rows

    conn.commit()
    conn.close()

    return {
        "stored_rows": total_rows,
        "tickers_processed": len(all_tickers) - len([f for f in failed if "recent" in f]),
        "tickers_failed": list(set(failed)),
        "date_range": " | ".join(date_ranges_fetched),
        "article_date_range": f"{article_min} to {article_max}" if article_min else "no articles",
        "timestamp": datetime.now().isoformat(),
    }
