"""
chart_service.py — High-Performance OHLCV & Events Service for TradingView / Lightweight Charts
================================================================================================
Phase 1: Provides clean, validated, point-in-time OHLCV bars and chart news/ML event annotations.

Key Guarantees:
1. lightweight-charts v5 format: UTC unix timestamp (seconds) for intraday, "YYYY-MM-DD" for daily/weekly.
2. Strict validation against yfinance limits (e.g. 1m <= 7d, 15m <= 60d, 1h <= 730d) returning clean 400s.
3. MultiIndex flattening, duplicate timestamp removal, NaN dropping, ascending sorting.
4. Thread-safe in-memory caching with TTL (60s intraday, 900s daily/weekly).
5. Mandatory disclaimer: "AI/model estimate — not investment advice. Delayed/unofficial data."
"""

from __future__ import annotations

import logging
import math
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False

from database import get_connection
from indian_stocks_master import INDIAN_STOCKS_DATA

logger = logging.getLogger("chart_service")

# ─────────────────────────────────────────────────────────────────────────────
# 1. ALLOWED INTERVALS, RANGES & YFINANCE LIMITS
# ─────────────────────────────────────────────────────────────────────────────

ALLOWED_INTERVALS = ["1m", "5m", "15m", "1h", "1d", "1wk"]

INTERVAL_ALLOWED_RANGES: Dict[str, List[str]] = {
    "1m": ["1d", "5d", "7d"],
    "5m": ["1d", "5d", "1mo", "60d"],
    "15m": ["1d", "5d", "1mo", "60d"],
    "1h": ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y"],
    "1d": ["1d", "5d", "1mo", "3mo", "6mo", "1y", "5y", "max"],
    "1wk": ["1mo", "3mo", "6mo", "1y", "5y", "max"],
}

DEFAULT_RANGE_PER_INTERVAL: Dict[str, str] = {
    "1m": "1d",
    "5m": "5d",
    "15m": "5d",
    "1h": "1mo",
    "1d": "1y",
    "1wk": "5y",
}

# Cache TTLs in seconds
INTRADAY_CACHE_TTL = 60      # 1 minute for 1m, 5m, 15m, 1h
DAILY_CACHE_TTL = 900       # 15 minutes for 1d, 1wk

_CHART_CACHE: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
_CACHE_LOCK = threading.Lock()


def clear_chart_cache() -> None:
    """Clear all entries in chart cache."""
    with _CACHE_LOCK:
        _CHART_CACHE.clear()


def validate_chart_params(interval: str, range_val: str) -> Tuple[str, str]:
    """
    Validate interval and range against yfinance API boundaries.
    Raises ValueError with descriptive guidance on failure.
    """
    int_clean = interval.strip().lower()
    if int_clean not in ALLOWED_INTERVALS:
        raise ValueError(
            f"Invalid interval '{interval}'. Allowed intervals: {', '.join(ALLOWED_INTERVALS)}"
        )

    rng_clean = range_val.strip().lower()
    allowed_ranges = INTERVAL_ALLOWED_RANGES[int_clean]
    if rng_clean not in allowed_ranges:
        raise ValueError(
            f"Invalid range '{range_val}' for interval '{int_clean}'. "
            f"Allowed ranges for {int_clean}: {', '.join(allowed_ranges)}"
        )

    return int_clean, rng_clean


# ─────────────────────────────────────────────────────────────────────────────
# 2. TICKER NORMALIZATION & SYMBOL MAPPING
# ─────────────────────────────────────────────────────────────────────────────

def normalize_ticker(ticker: str) -> str:
    """
    Normalize ticker to official Yahoo Finance symbol.
    Supports NSE (.NS), BSE (.BO), and indices (^NSEI, ^BSESN).
    Reuses indian_stocks_master catalog.
    """
    t = ticker.strip().upper().lstrip("$")

    # Already an index or full ticker
    if t.startswith("^") or t.endswith(".NS") or t.endswith(".BO") or t.endswith("=X") or t.endswith("=F"):
        return t

    # Check known index aliases
    index_map = {
        "NIFTY": "^NSEI",
        "NIFTY50": "^NSEI",
        "NIFTY 50": "^NSEI",
        "SENSEX": "^BSESN",
        "BSESENSEX": "^BSESN",
        "INDIAVIX": "^INDIAVIX",
        "VIX": "^INDIAVIX",
    }
    if t in index_map:
        return index_map[t]

    # Check Indian stocks master table
    for stock in INDIAN_STOCKS_DATA:
        if stock["symbol"].upper() == t:
            return stock["ticker"]
        for alias in stock.get("aliases", []):
            if alias.strip().upper() == t:
                return stock["ticker"]

    # Default to .NS for Indian equity symbols
    return f"{t}.NS"


# ─────────────────────────────────────────────────────────────────────────────
# 3. OHLCV FETCHING, PARSING & CACHING
# ─────────────────────────────────────────────────────────────────────────────

def _process_ohlcv_dataframe(df: pd.DataFrame, interval: str) -> List[Dict[str, Any]]:
    """
    Transforms raw yfinance DataFrame into lightweight-charts v5 format:
    - Flattens MultiIndex columns if present.
    - Drops NaNs in essential price columns.
    - Intraday: `time` is integer UTC seconds.
    - Daily/Weekly: `time` is "YYYY-MM-DD".
    - Deduplicates timestamps and sorts ascending.
    """
    if df is None or df.empty:
        return []

    # 1. Flatten MultiIndex if yfinance returned multi-level columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]

    # 2. Lowercase column names
    df.columns = [str(c).lower() for c in df.columns]

    # Required price columns
    required = ["open", "high", "low", "close"]
    for col in required:
        if col not in df.columns:
            return []

    # Add volume fallback if missing
    if "volume" not in df.columns:
        df["volume"] = 0

    # 3. Drop rows with NaNs in OHLC
    clean_df = df.dropna(subset=required).copy()
    if clean_df.empty:
        return []

    # Ensure numeric types
    for col in required + ["volume"]:
        clean_df[col] = pd.to_numeric(clean_df[col], errors="coerce")
    clean_df = clean_df.dropna(subset=required)

    is_intraday = interval in ("1m", "5m", "15m", "1h")

    # 4. Build bar list with strict timestamp formatting
    bars: List[Dict[str, Any]] = []
    seen_times = set()

    # Index can be DatetimeIndex
    for idx_val, row in clean_df.iterrows():
        try:
            # Parse datetime from index
            if isinstance(idx_val, (pd.Timestamp, datetime)):
                dt = idx_val
            else:
                dt = pd.to_datetime(idx_val)

            # Ensure UTC conversion for unix seconds
            if dt.tzinfo is None:
                # If naive, treat as UTC or local
                dt_utc = dt.replace(tzinfo=timezone.utc)
            else:
                dt_utc = dt.astimezone(timezone.utc)

            if is_intraday:
                time_val: Union[int, str] = int(dt_utc.timestamp())
            else:
                time_val = dt.strftime("%Y-%m-%d")

            # Deduplicate timestamp
            if time_val in seen_times:
                continue
            seen_times.add(time_val)

            c_val = float(row["close"])
            o_val = float(row["open"])
            h_val = float(row["high"])
            l_val = float(row["low"])
            v_val = float(row["volume"]) if not pd.isna(row["volume"]) else 0.0

            # Guard against invalid math
            if math.isnan(c_val) or math.isnan(o_val) or math.isnan(h_val) or math.isnan(l_val):
                continue

            bars.append({
                "time": time_val,
                "open": round(o_val, 2),
                "high": round(h_val, 2),
                "low": round(l_val, 2),
                "close": round(c_val, 2),
                "volume": int(v_val),
            })
        except Exception as e:
            logger.debug("Row parse error: %s", e)
            continue

    # 5. Sort ascending by time
    if is_intraday:
        bars.sort(key=lambda b: b["time"])
    else:
        bars.sort(key=lambda b: str(b["time"]))

    return bars


def get_chart_data(
    ticker: str,
    interval: str = "1d",
    range_val: Optional[str] = None,
    yf_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Fetch OHLCV chart bars with caching, parameter validation, and metadata.
    """
    clean_ticker = normalize_ticker(ticker)
    int_clean = interval.strip().lower()
    rng_clean = (range_val or DEFAULT_RANGE_PER_INTERVAL.get(int_clean, "1mo")).strip().lower()

    # Validate parameters
    int_clean, rng_clean = validate_chart_params(int_clean, rng_clean)

    cache_key = (clean_ticker, int_clean, rng_clean)
    now_ts = time.time()
    ttl = INTRADAY_CACHE_TTL if int_clean in ("1m", "5m", "15m", "1h") else DAILY_CACHE_TTL

    # 1. Check in-memory cache
    with _CACHE_LOCK:
        if cache_key in _CHART_CACHE:
            cached = _CHART_CACHE[cache_key]
            if now_ts - cached["timestamp"] < ttl:
                return cached["data"]

    # 2. Fetch from yfinance
    client = yf_client or yf
    try:
        t_obj = client.Ticker(clean_ticker)
        raw_df = t_obj.history(period=rng_clean, interval=int_clean, auto_adjust=False)
    except Exception as e:
        logger.error("yfinance chart fetch error for %s (%s, %s): %s", clean_ticker, int_clean, rng_clean, e)
        raise RuntimeError(f"Failed to fetch market data from provider: {e}")

    bars = _process_ohlcv_dataframe(raw_df, int_clean)

    # Last bar time
    last_bar_time = None
    if bars:
        last_b = bars[-1]
        last_bar_time = str(last_b["time"])

    response_payload = {
        "ticker": clean_ticker,
        "interval": int_clean,
        "range": rng_clean,
        "timezone": "Asia/Kolkata",
        "bars": bars,
        "meta": {
            "source": "yfinance (delayed/unofficial data)",
            "data_disclaimer": "AI/model estimate — not investment advice. Delayed/unofficial data.",
            "last_bar_time": last_bar_time,
            "bars_count": len(bars),
            "interval": int_clean,
            "range": rng_clean,
            "timezone": "Asia/Kolkata",
            "as_of": datetime.now(timezone.utc).isoformat(),
        },
    }

    # 3. Store in cache
    with _CACHE_LOCK:
        _CHART_CACHE[cache_key] = {"timestamp": now_ts, "data": response_payload}

    return response_payload


# ─────────────────────────────────────────────────────────────────────────────
# 4. CHART EVENTS (NEWS ARTICLES & ML SIGNALS ANNOTATIONS)
# ─────────────────────────────────────────────────────────────────────────────

def get_chart_events(
    ticker: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 40,
    conn: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Fetch news articles, sentiment direction, impact level, and ML predictions
    for chart markers / annotations.
    """
    clean_ticker = normalize_ticker(ticker)
    base_symbol = clean_ticker.replace(".NS", "").replace(".BO", "")

    db_conn = conn or get_connection()
    close_after = conn is None

    try:
        cur = db_conn.cursor()

        # Query articles and analyses for this ticker
        query = """
            SELECT a.id as article_id, a.title, a.published_at, a.source, a.url,
                   an.sentiment, an.direction, an.impact_level, an.confidence, an.event_type
            FROM articles a
            JOIN analysis an ON a.id = an.article_id
            WHERE (
                UPPER(an.ticker) = ?
                OR UPPER(an.ticker) = ?
                OR UPPER(a.ticker) = ?
                OR UPPER(a.ticker) = ?
                OR an.company_name LIKE ?
            )
        """
        params: List[Any] = [clean_ticker, base_symbol, clean_ticker, base_symbol, f"%{base_symbol}%"]

        if from_date:
            query += " AND a.published_at >= ?"
            params.append(from_date)
        if to_date:
            query += " AND a.published_at <= ?"
            params.append(to_date)

        query += " ORDER BY a.published_at DESC LIMIT ?"
        params.append(int(limit))

        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        events: List[Dict[str, Any]] = []

        for row in rows:
            art_id = row["article_id"]
            pub_at = row["published_at"] or ""

            # Convert published_at to UTC unix timestamp in seconds
            time_sec = None
            date_str = None
            try:
                # Handle ISO formats
                clean_pub = pub_at.replace("Z", "+00:00")
                if "T" in clean_pub:
                    dt = datetime.fromisoformat(clean_pub)
                else:
                    dt = datetime.strptime(clean_pub[:19], "%Y-%m-%d %H:%M:%S")
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                time_sec = int(dt.timestamp())
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                time_sec = int(time.time())
                date_str = datetime.now().strftime("%Y-%m-%d")

            # Look up ML predictions if stored
            cur.execute("""
                SELECT horizon, predicted_class, prob_positive, prob_neutral, prob_negative
                FROM prediction
                WHERE article_id = ?
            """, (art_id,))
            preds_rows = cur.fetchall()
            ml_preds = {}
            for p in preds_rows:
                ml_preds[p["horizon"]] = {
                    "predicted_class": p["predicted_class"],
                    "prob_positive": round(float(p["prob_positive"] or 0.0), 3),
                    "prob_neutral": round(float(p["prob_neutral"] or 0.0), 3),
                    "prob_negative": round(float(p["prob_negative"] or 0.0), 3),
                }

            events.append({
                "id": art_id,
                "article_id": art_id,
                "time": time_sec,
                "date": date_str,
                "published_at": pub_at,
                "title": row["title"],
                "source": row["source"],
                "url": row["url"],
                "sentiment": row["sentiment"],
                "direction": row["direction"],
                "impact": row["impact_level"],
                "confidence": round(float(row["confidence"] or 0.0), 1),
                "event_type": row["event_type"],
                "ml_predictions": ml_preds,
            })

        # Sort ascending by time so chart markers display chronologically
        events.sort(key=lambda x: x["time"])

        return {
            "ticker": clean_ticker,
            "events": events,
            "total": len(events),
            "disclaimer": "AI/model estimate — not investment advice.",
        }
    finally:
        if close_after:
            db_conn.close()
