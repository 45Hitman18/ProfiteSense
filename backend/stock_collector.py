"""
stock_collector.py — Fetch and store OHLCV historical data via yfinance.
Called during /api/ml/collect-prices or on demand.
Covers BOTH recent 90-day data AND historical clusters of articles in the DB
so the ML labeling pipeline can match articles to actual future price returns.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Callable

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


def _get_article_windows(period_days: int = DEFAULT_PERIOD_DAYS) -> List[tuple]:
    """
    Find distinct time windows needed for price collection:
    1. Recent window (past period_days up to tomorrow)
    2. Discrete historical windows around article publication dates (e.g., April 2024, Oct 2016)
       padded with 10 days after for 5-day horizon labels.
    """
    now = datetime.now()
    recent_start = (now - timedelta(days=period_days)).strftime("%Y-%m-%d")
    recent_end = (now + timedelta(days=2)).strftime("%Y-%m-%d")
    windows = [(recent_start, recent_end, "recent")]

    conn = get_connection()
    rows = conn.execute("""
        SELECT a.published_at
        FROM articles a
        JOIN analysis an ON a.id = an.article_id
        WHERE an.ticker IS NOT NULL AND a.published_at IS NOT NULL
          AND length(a.published_at) >= 8
    """).fetchall()
    conn.close()

    months = set()
    for r in rows:
        raw = str(r[0])
        try:
            if 'T' in raw:
                d = raw.split('T')[0]
            else:
                d = raw[:10]
            if len(d) == 8 and '-' not in d:
                d = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
            if len(d) == 10:
                months.add(d[:7])  # e.g., '2024-04', '2016-10'
        except Exception:
            continue

    for ym in sorted(months):
        try:
            y, m = map(int, ym.split('-'))
            month_start = datetime(y, m, 1)
            # month end: approx 35 days later
            month_end = (month_start + timedelta(days=35)).replace(day=1) + timedelta(days=14)
            start_str = (month_start - timedelta(days=5)).strftime("%Y-%m-%d")
            end_str = month_end.strftime("%Y-%m-%d")
            if end_str < recent_start:
                windows.append((start_str, end_str, f"historical_{ym}"))
        except Exception:
            continue

    return windows


def _fetch_ticker(ticker: str, start: str, end: str, conn) -> int:
    """Fetch and store price data for one ticker. Returns number of rows stored."""
    try:
        data = yf.download(ticker, start=start, end=end,
                           auto_adjust=True, progress=False, threads=False)
        if data is None or data.empty:
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


def fetch_and_store_prices(
    tickers: list = None,
    period_days: int = DEFAULT_PERIOD_DAYS,
    on_progress: Optional[Callable[[int, int, str, str], None]] = None
) -> dict:
    """
    Download OHLCV from yfinance for all tracked tickers.

    Fetches targeted windows:
    1. Recent 90-day window (for current/future labeling)
    2. Discrete historical windows matching article publication dates
       (e.g., April 2024, Oct 2016)

    Calls on_progress(current_step, total_steps, ticker, message) if provided.
    """
    if not HAS_YF:
        return {"error": "yfinance not installed"}

    if tickers is None:
        tickers = get_tracked_tickers()

    if not tickers:
        return {"stored_rows": 0, "tickers": [], "message": "No tickers with analysis data found."}

    fetch_windows = _get_article_windows(period_days)

    # Always include market indices
    index_tickers = ["^NSEI", "SPY", "^BSESN"]
    all_tickers = list(set(tickers + index_tickers))

    conn = get_connection()
    total_rows = 0
    failed = []
    date_ranges_fetched = []

    total_tasks = len(fetch_windows) * len(all_tickers)
    current_task = 0

    for (start, end, window_label) in fetch_windows:
        logger.info("Fetching %s window: %s to %s (%d tickers)", window_label, start, end, len(all_tickers))
        date_ranges_fetched.append(f"{start} to {end} [{window_label}]")

        for ticker in all_tickers:
            current_task += 1
            if on_progress:
                on_progress(
                    current_task,
                    total_tasks,
                    ticker,
                    f"Fetching {ticker} for {window_label} ({current_task}/{total_tasks})..."
                )

            rows = _fetch_ticker(ticker, start, end, conn)
            if rows == 0 and ticker not in index_tickers:
                failed.append(f"{ticker}({window_label})")
            total_rows += rows

    conn.commit()
    conn.close()

    if on_progress:
        on_progress(total_tasks, total_tasks, "COMPLETE", f"Finished! Stored {total_rows} total rows.")

    return {
        "status": "completed",
        "stored_rows": total_rows,
        "tickers_processed": len(all_tickers) - len([f for f in failed if "recent" in f]),
        "tickers_failed": list(set(failed)),
        "date_range": " | ".join(date_ranges_fetched),
        "windows_count": len(fetch_windows),
        "timestamp": datetime.now().isoformat(),
        "message": f"Successfully collected {total_rows} price rows across {len(fetch_windows)} time windows for {len(all_tickers)} tickers.",
    }
