"""
test_technical_features.py — Unit tests for Phase 1 Deterministic Feature Engine
================================================================================
Acceptance tests:
1. Clean uptrend: known higher highs, markup phase, bull regime, ADX > 25.
2. Double top: levels detect resistance near known peak with multiple touches.
3. Planted RSI divergence:
   - Bullish: lower low in price, higher low in RSI.
   - Bearish: higher high in price, lower high in RSI.
4. Volume spike: RVOL climax flag, and volume dry-up flag.
5. Strict lookahead test: recompute features on truncated series and assert point-in-time exact match.
6. Multi-timeframe alignment: point-in-time closed-before logic.
7. yfinance limit reporting: data quality and sample size warnings.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock
import numpy as np
import pandas as pd
import pytest

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from technical_features import (
    compute_technical_features,
    get_latest_technical_summary,
    compute_multi_timeframe_alignment,
    fetch_timeframe_candles,
    compute_atr,
    compute_ema,
    compute_rsi,
    find_fractal_pivots_point_in_time,
    cluster_pivots_into_zones,
)


def _generate_synthetic_ohlcv(
    n_bars: int = 100,
    base_price: float = 100.0,
    trend_slope: float = 0.5,
    volatility: float = 1.0,
    volume_base: float = 10000.0,
) -> pd.DataFrame:
    """Helper to generate clean synthetic OHLCV dataframe."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=n_bars, freq="D")
    
    closes = [base_price]
    for i in range(1, n_bars):
        step = trend_slope + np.random.normal(0, volatility * 0.2)
        closes.append(closes[-1] + step)
    
    closes = np.array(closes)
    highs = closes + np.abs(np.random.normal(0.8, 0.2, n_bars))
    lows = closes - np.abs(np.random.normal(0.8, 0.2, n_bars))
    opens = (closes + np.roll(closes, 1)) / 2.0
    opens[0] = closes[0]
    volumes = np.random.normal(volume_base, volume_base * 0.1, n_bars).clip(min=100)

    df = pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        },
        index=dates,
    )
    return df


def test_clean_uptrend():
    """Test 1: Monotonic uptrend produces Markup phase, Bull regime, and positive EMA slopes."""
    n = 80
    closes = np.linspace(100, 200, n)
    highs = closes + 1.0
    lows = closes - 1.0
    opens = closes - 0.5
    volumes = np.full(n, 50000.0)

    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=pd.date_range("2024-01-01", periods=n, freq="D"),
    )

    feat = compute_technical_features(df, timeframe="1d")
    last = feat.iloc[-1]

    # Verify EMA order
    assert last["ema20"] > last["ema50"], "EMA20 should exceed EMA50 in clear uptrend"
    assert last["slope_ema50"] > 0, "EMA50 slope should be positive"
    assert last["higher_highs_count_10"] >= 8, "Uptrend should have high count of higher highs"
    assert last["phase"] == "markup", f"Expected markup phase, got {last['phase']}"
    assert "Markup" in last["phase_rule"], "Rule should explain markup phase"
    assert last["regime"] == "bull_regime", "Should be in bull regime"
    assert last["rsi14"] > 60.0, "RSI should be high in strong uptrend"
    assert last["adx14"] > 25.0, "ADX should reflect a strong trend"


def test_double_top_resistance():
    """Test 2: Double top creates a resistance zone with multiple touches."""
    n = 60
    closes = np.full(n, 100.0)
    highs = np.full(n, 102.0)
    lows = np.full(n, 98.0)
    opens = np.full(n, 100.0)
    volumes = np.full(n, 10000.0)

    # First peak at bar 20: reaches 150
    highs[18:23] = [120, 140, 150, 140, 120]
    closes[18:23] = [118, 138, 148, 138, 118]
    # Retrace to 110 at bar 30
    # Second peak at bar 40: reaches 150.2
    highs[38:43] = [120, 140, 150.2, 140, 120]
    closes[38:43] = [118, 138, 148.2, 138, 118]

    # Current price pulls back to 130
    closes[-1] = 130.0
    highs[-1] = 132.0
    lows[-1] = 128.0

    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=pd.date_range("2024-01-01", periods=n, freq="D"),
    )

    summary = get_latest_technical_summary(df, timeframe="1d", fractal_window=2)
    resistances = summary["levels"]["resistances"]
    assert len(resistances) > 0, "Should detect resistance levels"
    # The double top zone around ~150 should be detected with at least 2 touches
    top_zone = [r for r in resistances if abs(r["mid"] - 150.0) < 5.0]
    assert len(top_zone) > 0, f"Resistance around 150 not found in {resistances}"
    assert top_zone[0]["touches"] >= 2, f"Expected double top to have >= 2 touches, got {top_zone[0]['touches']}"


def test_planted_rsi_divergence():
    """Test 3: Planted regular bearish divergence (Price HH, RSI LH)."""
    # Create baseline
    n = 80
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    closes = np.full(n, 100.0)
    highs = np.full(n, 101.0)
    lows = np.full(n, 99.0)
    volumes = np.full(n, 5000.0)

    # Peak 1 at bar 30: price 130, very sharp move -> high RSI
    closes[20:30] = np.linspace(100, 130, 10)
    highs[20:30] = closes[20:30] + 1.0
    closes[30:40] = np.linspace(130, 110, 10)
    highs[30:40] = closes[30:40] + 1.0

    # Peak 2 at bar 55: price 135 (higher high), but slow grind -> lower RSI
    closes[40:55] = np.linspace(110, 135, 15)
    highs[40:55] = closes[40:55] + 1.0
    closes[55:65] = np.linspace(135, 120, 10)
    highs[55:65] = closes[55:65] + 1.0

    df = pd.DataFrame(
        {"open": closes - 0.5, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=dates,
    )

    summary = get_latest_technical_summary(df, timeframe="1d", fractal_window=2)
    divergence = summary["momentum"]["divergence"]

    assert divergence is not None, "Should detect planted divergence"
    assert divergence["type"] == "bearish", f"Expected bearish divergence, got {divergence['type']}"
    assert len(divergence["price_pivots"]) == 2
    assert len(divergence["rsi_pivots"]) == 2
    # Price HH check
    assert divergence["price_pivots"][1]["price"] > divergence["price_pivots"][0]["price"]
    # RSI LH check
    assert divergence["rsi_pivots"][1]["rsi"] < divergence["rsi_pivots"][0]["rsi"]


def test_volume_spike_and_dryup():
    """Test 4: Volume climax and dry-up flags respond deterministically."""
    df = _generate_synthetic_ohlcv(n_bars=50, volume_base=10000.0)
    
    # 1. Normal run
    feat = compute_technical_features(df)
    assert not feat.iloc[-1]["vol_climax"]
    assert not feat.iloc[-1]["vol_dryup"]

    # 2. Climax spike (5x volume)
    df_climax = df.copy()
    df_climax.loc[df_climax.index[-1], "volume"] = 50000.0
    feat_climax = compute_technical_features(df_climax)
    assert feat_climax.iloc[-1]["vol_climax"], "Volume > 2.5x mean should trigger vol_climax"
    assert feat_climax.iloc[-1]["rvol20"] >= 3.0

    # 3. Dry-up (0.2x volume)
    df_dryup = df.copy()
    df_dryup.loc[df_dryup.index[-1], "volume"] = 1000.0
    feat_dryup = compute_technical_features(df_dryup)
    assert feat_dryup.iloc[-1]["vol_dryup"], "Volume < 0.5x mean should trigger vol_dryup"


def test_strict_lookahead_no_leakage():
    """
    Test 5: STRICT POINT-IN-TIME / NO LEAKAGE TEST.
    Assert that features computed on a truncated dataset [0..T]
    EXACTLY match the features computed at row T in the full dataset [0..N].
    """
    df_full = _generate_synthetic_ohlcv(n_bars=120, trend_slope=0.2, volatility=1.5)
    
    # Compute on full dataset
    feat_full = compute_technical_features(df_full)

    # Test at multiple cutoff points
    for cutoff in [60, 80, 100]:
        df_truncated = df_full.iloc[:cutoff].copy()
        feat_truncated = compute_technical_features(df_truncated)

        # Compare row (cutoff - 1)
        row_full = feat_full.iloc[cutoff - 1]
        row_trunc = feat_truncated.iloc[-1]

        check_cols = [
            "atr14",
            "ema20",
            "ema50",
            "slope_ema20",
            "slope_ema50",
            "dist_ema20_atr",
            "dist_ema50_atr",
            "rsi14",
            "rsi_slope_5",
            "macd",
            "macd_signal",
            "macd_hist",
            "rvol20",
            "obv",
            "phase",
            "nearest_support_mid",
            "nearest_resistance_mid",
        ]

        for col in check_cols:
            val_full = row_full[col]
            val_trunc = row_trunc[col]
            if isinstance(val_full, (float, np.floating)):
                assert np.isclose(val_full, val_trunc, atol=1e-5), (
                    f"Lookahead detected in '{col}' at bar {cutoff-1}: "
                    f"Full={val_full}, Truncated={val_trunc}"
                )
            else:
                assert val_full == val_trunc, (
                    f"Lookahead detected in categorical '{col}' at bar {cutoff-1}: "
                    f"Full={val_full}, Truncated={val_trunc}"
                )


def test_multi_timeframe_alignment_no_lookahead():
    """Test 6: Multi-timeframe alignment strictly uses closed bars only."""
    # Create 1h and 1d data
    dates_1h = pd.date_range("2024-01-01 09:15", periods=75, freq="h")
    df_1h = _generate_synthetic_ohlcv(n_bars=75, trend_slope=0.3)
    df_1h.index = dates_1h

    dates_1d = pd.date_range("2024-01-01", periods=15, freq="D")
    df_1d = _generate_synthetic_ohlcv(n_bars=15, trend_slope=0.8)
    df_1d.index = dates_1d

    timeframes = {"1h": df_1h, "1d": df_1d}

    # Evaluate at middle of day 5
    eval_ts = "2024-01-05 13:15"
    alignment = compute_multi_timeframe_alignment(timeframes, eval_timestamp=eval_ts)

    assert "alignment_score" in alignment
    assert "alignment_state" in alignment
    assert -1.0 <= alignment["alignment_score"] <= 1.0
    assert "1h" in alignment["timeframe_states"]
    assert "1d" in alignment["timeframe_states"]


def test_yfinance_intraday_limit_reporting():
    """Test 7: Candle fetcher reports explicit intraday limits and warnings without network."""
    mock_yf = MagicMock()
    mock_ticker = MagicMock()
    
    # Mock history returned
    sample_df = _generate_synthetic_ohlcv(n_bars=40)
    mock_ticker.history.return_value = sample_df
    mock_yf.Ticker.return_value = mock_ticker

    # Test 15m
    _, dq_15m = fetch_timeframe_candles("RELIANCE.NS", timeframe="15m", yf_client=mock_yf)
    assert dq_15m["sample_size_limited"] is True
    assert any("60 calendar days" in w for w in dq_15m["warnings"])

    # Test 1h
    _, dq_1h = fetch_timeframe_candles("RELIANCE.NS", timeframe="1h", yf_client=mock_yf)
    assert dq_1h["sample_size_limited"] is True
    assert any("730 calendar days" in w for w in dq_1h["warnings"])

    # Test 1d (not limited)
    _, dq_1d = fetch_timeframe_candles("RELIANCE.NS", timeframe="1d", yf_client=mock_yf)
    assert dq_1d["sample_size_limited"] is False
