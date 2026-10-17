"""
test_chart_service.py — Unit Tests for TradingView / Lightweight Charts OHLCV & Events Service
=============================================================================================
Phase 1 Acceptance Tests:
1. Validation errors: invalid interval, out-of-bounds range for interval (e.g. 1m with 1y, 15m with 1y).
2. Time formats: integer UTC seconds for intraday (1m, 5m, 15m, 1h), 'YYYY-MM-DD' string for daily/weekly.
3. Deduplication, sorting ascending, NaN dropping, MultiIndex flattening.
4. In-memory caching and request throttling (mock yfinance, zero network hits).
5. FastAPI endpoints: GET /api/chart/{ticker} and GET /api/chart/{ticker}/events.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
import pytest
from fastapi.testclient import TestClient

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from chart_service import (
    validate_chart_params,
    normalize_ticker,
    _process_ohlcv_dataframe,
    get_chart_data,
    get_chart_events,
    clear_chart_cache,
    ALLOWED_INTERVALS,
    INTERVAL_ALLOWED_RANGES,
)
from main import app

client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# 1. PARAMETER VALIDATION TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_validate_chart_params_valid():
    """Valid interval and range combinations pass validation."""
    assert validate_chart_params("1m", "1d") == ("1m", "1d")
    assert validate_chart_params("5m", "5d") == ("5m", "5d")
    assert validate_chart_params("15m", "1mo") == ("15m", "1mo")
    assert validate_chart_params("1h", "6mo") == ("1h", "6mo")
    assert validate_chart_params("1d", "1y") == ("1d", "1y")
    assert validate_chart_params("1wk", "5y") == ("1wk", "5y")


def test_validate_chart_params_invalid_interval():
    """Invalid interval raises ValueError listing allowed intervals."""
    with pytest.raises(ValueError) as exc:
        validate_chart_params("2m", "1d")
    assert "Invalid interval '2m'" in str(exc.value)
    assert "1m, 5m, 15m, 1h, 1d, 1wk" in str(exc.value)


def test_validate_chart_params_out_of_bounds_range():
    """
    Exceeding yfinance interval boundaries raises clear error with allowed ranges.
    e.g. 1m is capped at ~7d, 15m at ~60d, 1h at ~730d.
    """
    # 1m cannot request 1mo
    with pytest.raises(ValueError) as exc:
        validate_chart_params("1m", "1mo")
    assert "Invalid range '1mo' for interval '1m'" in str(exc.value)
    assert "1d, 5d, 7d" in str(exc.value)

    # 15m cannot request 1y
    with pytest.raises(ValueError) as exc:
        validate_chart_params("15m", "1y")
    assert "Invalid range '1y' for interval '15m'" in str(exc.value)
    assert "1d, 5d, 1mo" in str(exc.value)

    # 1h cannot request 5y
    with pytest.raises(ValueError) as exc:
        validate_chart_params("1h", "5y")
    assert "Invalid range '5y' for interval '1h'" in str(exc.value)


def test_normalize_ticker():
    """Symbol mapping supports plain symbols, NSE (.NS), BSE (.BO), and indices."""
    assert normalize_ticker("RELIANCE") == "RELIANCE.NS"
    assert normalize_ticker("TCS.NS") == "TCS.NS"
    assert normalize_ticker("500325.BO") == "500325.BO"
    assert normalize_ticker("NIFTY") == "^NSEI"
    assert normalize_ticker("SENSEX") == "^BSESN"
    assert normalize_ticker("^NSEI") == "^NSEI"


# ─────────────────────────────────────────────────────────────────────────────
# 2. OHLCV DATAFRAME TRANSFORMATION & DEDUPE TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_process_ohlcv_intraday_time_format():
    """Intraday intervals (1m, 5m, 15m, 1h) format time as integer UTC seconds."""
    dates = pd.date_range("2024-04-01 09:15:00", periods=5, freq="15min", tz="Asia/Kolkata")
    df = pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "High": [105.0, 106.0, 107.0, 108.0, 109.0],
            "Low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "Close": [104.0, 105.0, 106.0, 107.0, 108.0],
            "Volume": [1000, 1200, 1400, 1600, 1800],
        },
        index=dates,
    )

    bars = _process_ohlcv_dataframe(df, interval="15m")
    assert len(bars) == 5
    for bar in bars:
        assert isinstance(bar["time"], int), f"Intraday bar time must be integer UTC seconds: {bar['time']}"
        assert bar["time"] > 1700000000
    # Strictly sorted ascending
    times = [b["time"] for b in bars]
    assert times == sorted(times)


def test_process_ohlcv_daily_time_format():
    """Daily and weekly intervals format time as 'YYYY-MM-DD' strings."""
    dates = pd.date_range("2024-04-01", periods=5, freq="D")
    df = pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "High": [105.0, 106.0, 107.0, 108.0, 109.0],
            "Low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "Close": [104.0, 105.0, 106.0, 107.0, 108.0],
            "Volume": [1000, 1200, 1400, 1600, 1800],
        },
        index=dates,
    )

    bars = _process_ohlcv_dataframe(df, interval="1d")
    assert len(bars) == 5
    assert bars[0]["time"] == "2024-04-01"
    assert bars[-1]["time"] == "2024-04-05"


def test_process_ohlcv_deduplication_and_nan_drop():
    """Duplicate timestamps are deduplicated and NaN rows are dropped."""
    # Dates with duplicate 2024-04-02
    dates = pd.to_datetime(["2024-04-01", "2024-04-02", "2024-04-02", "2024-04-03", "2024-04-04"])
    df = pd.DataFrame(
        {
            "Open": [100.0, 101.0, 101.5, np.nan, 104.0],  # Bar 3 has NaN open
            "High": [105.0, 106.0, 106.5, 108.0, 109.0],
            "Low": [99.0, 100.0, 100.5, 102.0, 103.0],
            "Close": [104.0, 105.0, 105.5, 107.0, 108.0],
            "Volume": [1000, 1200, 1300, 1600, 1800],
        },
        index=dates,
    )

    bars = _process_ohlcv_dataframe(df, interval="1d")
    # Expected: 2024-04-01, single 2024-04-02 (deduped), 2024-04-03 dropped (NaN), 2024-04-04
    assert len(bars) == 3
    times = [b["time"] for b in bars]
    assert times == ["2024-04-01", "2024-04-02", "2024-04-04"]


def test_process_ohlcv_multiindex_flattening():
    """yfinance MultiIndex columns are cleanly flattened."""
    dates = pd.date_range("2024-04-01", periods=3, freq="D")
    tuples = [("Open", "RELIANCE.NS"), ("High", "RELIANCE.NS"), ("Low", "RELIANCE.NS"), ("Close", "RELIANCE.NS"), ("Volume", "RELIANCE.NS")]
    columns = pd.MultiIndex.from_tuples(tuples)
    df = pd.DataFrame(
        [
            [100.0, 105.0, 99.0, 104.0, 1000],
            [101.0, 106.0, 100.0, 105.0, 1200],
            [102.0, 107.0, 101.0, 106.0, 1400],
        ],
        index=dates,
        columns=columns,
    )

    bars = _process_ohlcv_dataframe(df, interval="1d")
    assert len(bars) == 3
    assert bars[0]["close"] == 104.0


# ─────────────────────────────────────────────────────────────────────────────
# 3. CACHING & THROTTLING TESTS (MOCK YFINANCE)
# ─────────────────────────────────────────────────────────────────────────────

def test_chart_data_caching():
    """In-memory cache prevents redundant yfinance calls within TTL."""
    clear_chart_cache()

    mock_yf = MagicMock()
    mock_ticker = MagicMock()
    dates = pd.date_range("2024-04-01", periods=3, freq="D")
    sample_df = pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0],
            "High": [105.0, 106.0, 107.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [104.0, 105.0, 106.0],
            "Volume": [1000, 1200, 1400],
        },
        index=dates,
    )
    mock_ticker.history.return_value = sample_df
    mock_yf.Ticker.return_value = mock_ticker

    # Call 1: Misses cache -> calls yfinance history once
    data1 = get_chart_data("TCS.NS", interval="1d", range_val="1mo", yf_client=mock_yf)
    assert len(data1["bars"]) == 3
    assert mock_ticker.history.call_count == 1

    # Call 2: Hits cache -> does NOT call yfinance history again
    data2 = get_chart_data("TCS.NS", interval="1d", range_val="1mo", yf_client=mock_yf)
    assert len(data2["bars"]) == 3
    assert mock_ticker.history.call_count == 1

    # Clear cache -> Call 3 calls yfinance history
    clear_chart_cache()
    data3 = get_chart_data("TCS.NS", interval="1d", range_val="1mo", yf_client=mock_yf)
    assert mock_ticker.history.call_count == 2


# ─────────────────────────────────────────────────────────────────────────────
# 4. FASTAPI ENDPOINT ACCEPTANCE TESTS
# ─────────────────────────────────────────────────────────────────────────────

@patch("chart_service.yf")
def test_api_chart_endpoint_success(mock_yf):
    """GET /api/chart/{ticker} returns 200 with bars, meta, and compliance disclaimer."""
    clear_chart_cache()
    mock_ticker = MagicMock()
    dates = pd.date_range("2024-04-01", periods=4, freq="D")
    sample_df = pd.DataFrame(
        {
            "Open": [2500.0, 2510.0, 2520.0, 2530.0],
            "High": [2520.0, 2530.0, 2540.0, 2550.0],
            "Low": [2490.0, 2500.0, 2510.0, 2520.0],
            "Close": [2515.0, 2525.0, 2535.0, 2545.0],
            "Volume": [50000, 52000, 48000, 51000],
        },
        index=dates,
    )
    mock_ticker.history.return_value = sample_df
    mock_yf.Ticker.return_value = mock_ticker

    resp = client.get("/api/chart/RELIANCE?interval=1d&range=1mo")
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["ticker"] == "RELIANCE.NS"
    assert payload["interval"] == "1d"
    assert payload["timezone"] == "Asia/Kolkata"
    assert len(payload["bars"]) == 4
    assert payload["bars"][0]["close"] == 2515.0

    # Verify metadata and disclaimer
    meta = payload["meta"]
    assert meta["source"] == "yfinance (delayed/unofficial data)"
    assert "AI/model estimate — not investment advice" in meta["data_disclaimer"]
    assert meta["bars_count"] == 4
    assert meta["last_bar_time"] == "2024-04-04"


def test_api_chart_endpoint_validation_error():
    """GET /api/chart/{ticker} returns 400 when interval or range violates boundaries."""
    # Invalid interval
    resp_bad_int = client.get("/api/chart/RELIANCE?interval=3m&range=1d")
    assert resp_bad_int.status_code == 400
    assert "Invalid interval '3m'" in resp_bad_int.json()["detail"]

    # Exceeding interval range limit (1m with 1mo)
    resp_bad_rng = client.get("/api/chart/RELIANCE?interval=1m&range=1mo")
    assert resp_bad_rng.status_code == 400
    assert "Invalid range '1mo' for interval '1m'" in resp_bad_rng.json()["detail"]


def test_api_chart_events_endpoint():
    """GET /api/chart/{ticker}/events returns article annotations and ML predictions."""
    resp = client.get("/api/chart/RELIANCE/events?limit=10")
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["ticker"] == "RELIANCE.NS"
    assert "events" in payload
    assert "total" in payload
    assert "disclaimer" in payload

    # If DB has events for RELIANCE, verify event schema
    if payload["events"]:
        evt = payload["events"][0]
        assert "id" in evt
        assert "time" in evt
        assert "title" in evt
        assert "sentiment" in evt
        assert "direction" in evt
        assert "impact" in evt
        assert "ml_predictions" in evt
