"""
stock_collector.py — Fetch and store OHLCV historical data via yfinance.
Called during /api/ml/collect-prices or on demand.
Only fetches data for tickers that have analysis records.
"""
import logging
from datetime import datetime, timedelta
from typing import List

logger = logging.getLogger("stock_collector")

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False

from database import get_connection

# Default period to fetch (gives enough for volatility + labeled outcomes)
DEFAULT_PERIOD_DAYS = 90


def get_tracked_tickers() -> List[str]:
    """Get all unique tickers that have analysis rows."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT ticker FROM analysis WHERE ticker IS NOT NULL AND ticker != ''"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]


def fetch_and_store_prices(tickers: List[str] = None, period_days: int = DEFAULT_PERIOD_DAYS) -> dict:
    """Download OHLCV from yfinance and insert into stock_price table."""
    if not HAS_YF:
        return {"error": "yfinance not installed"}

    if tickers is None:
        tickers = get_tracked_tickers()

    if not tickers:
        return {"stored": 0, "tickers": [], "message": "No tickers with analysis data found."}

    start = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")
    end   = datetime.now().strftime("%Y-%m-%d")

    # Always include market indices for market_trend feature
    index_tickers = ["^NSEI", "SPY"]
    all_tickers = list(set(tickers + index_tickers))

    conn = get_connection()
    total_rows = 0
    failed = []

    for ticker in all_tickers:
        try:
            data = yf.download(ticker, start=start, end=end,
                               auto_adjust=True, progress=False, threads=False)
            if data.empty:
                logger.warning("No data for %s", ticker)
                failed.append(ticker)
                continue

            for date, row in data.iterrows():
                date_str = date.strftime("%Y-%m-%d")
                # Handle MultiIndex columns from yfinance
                def _get(col):
                    try:
                        val = row[col]
                        if hasattr(val, 'item'):
                            return float(val.item())
                        return float(val)
                    except Exception:
                        return None

                conn.execute("""
                    INSERT OR IGNORE INTO stock_price
                    (ticker, date, open, high, low, close, volume, adj_close)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (
                    ticker, date_str,
                    _get("Open"), _get("High"), _get("Low"),
                    _get("Close"), _get("Volume"), _get("Close"),
                ))
                total_rows += 1

            logger.info("Stored %s price rows for %s", len(data), ticker)
        except Exception as e:
            logger.error("Price fetch failed for %s: %s", ticker, e)
            failed.append(ticker)

    conn.commit()
    conn.close()

    return {
        "stored_rows": total_rows,
        "tickers_processed": len(all_tickers) - len(failed),
        "tickers_failed": failed,
        "date_range": f"{start} to {end}",
        "timestamp": datetime.now().isoformat(),
    }
