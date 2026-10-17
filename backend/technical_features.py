"""
technical_features.py — Deterministic Multi-Timeframe Feature Engine for Indian Equities
========================================================================================
Phase 1: Pure OHLCV deterministic feature engine with zero LLM guessing.

Key Principles:
1. Strict point-in-time calculation: a row at time t may use ONLY data up to and including t's close.
2. Complete coverage: Trend, Phase, Levels, Momentum, Volume, Multi-Timeframe Alignment.
3. Explainable rule-based Phase classification and level zone scoring.
4. Divergence detection returning pivot indices for chart visualization.
5. Intraday sample size limit reporting (yfinance boundaries).
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger("technical_features")

# ─────────────────────────────────────────────────────────────────────────────
# 1. CORE MATH HELPERS (REUSED / STANDARDIZED INDICATORS)
# ─────────────────────────────────────────────────────────────────────────────

def compute_atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """
    Wilder's smoothed Average True Range (ATR).
    Formula:
      TR = max(H - L, |H - prev_C|, |L - prev_C|)
      ATR_t = (ATR_{t-1} * (period - 1) + TR_t) / period
    """
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Initial SMA seed followed by Wilder exponential smoothing (alpha = 1/period)
    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    # For initial bars where period is not reached, fall back to expanding mean
    atr = atr.fillna(tr.expanding(min_periods=1).mean())
    return atr


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    """Standard Exponential Moving Average."""
    return series.ewm(span=span, adjust=False).mean()


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index (Wilder's RSI).
    Matches classical technical analysis standard.
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    # Fill initial periods
    avg_gain = avg_gain.fillna(gain.expanding(min_periods=1).mean())
    avg_loss = avg_loss.fillna(loss.expanding(min_periods=1).mean())

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Edge cases: 0 loss -> 100 RSI, 0 gain & 0 loss -> 50 RSI
    rsi = rsi.where(avg_loss != 0.0, 100.0)
    rsi = rsi.where((avg_gain != 0.0) | (avg_loss != 0.0), 50.0)
    return rsi.fillna(50.0)


def compute_adx(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Wilder's Average Directional Index (ADX) along with +DI and -DI.
    Returns (adx, plus_di, minus_di).
    """
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=high.index
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=low.index
    )

    tr = compute_atr(high, low, close, period=1)  # Raw 1-bar true range

    # Wilder smooth TR, +DM, -DM
    smooth_tr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    smooth_pdm = plus_dm.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    smooth_mdm = minus_dm.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    # Avoid div zero
    smooth_tr_safe = smooth_tr.replace(0.0, np.nan)
    plus_di = (100.0 * smooth_pdm / smooth_tr_safe).fillna(0.0)
    minus_di = (100.0 * smooth_mdm / smooth_tr_safe).fillna(0.0)

    di_sum = (plus_di + minus_di).replace(0.0, np.nan)
    dx = (100.0 * (plus_di - minus_di).abs() / di_sum).fillna(0.0)

    adx = dx.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean().fillna(0.0)
    return adx, plus_di, minus_di


def compute_macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Moving Average Convergence Divergence (MACD, Signal, Histogram)."""
    ema_fast = compute_ema(close, fast)
    ema_slow = compute_ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = compute_ema(macd_line, signal)
    macd_hist = macd_line - signal_line
    return macd_line, signal_line, macd_hist


def compute_bollinger_bands(
    close: pd.Series, period: int = 20, num_std: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Bollinger Bands and Bandwidth.
    Returns (upper, mid, lower, bandwidth).
    bandwidth = (upper - lower) / mid
    """
    mid = close.rolling(window=period, min_periods=1).mean()
    std = close.rolling(window=period, min_periods=1).std(ddof=0).fillna(0.0)
    upper = mid + num_std * std
    lower = mid - num_std * std
    bw = (upper - lower) / mid.replace(0.0, np.nan)
    return upper, mid, lower, bw.fillna(0.0)


# ─────────────────────────────────────────────────────────────────────────────
# 2. FRACTALS, PIVOTS, AND CLUSTERING (POINT-IN-TIME)
# ─────────────────────────────────────────────────────────────────────────────

def find_fractal_pivots_point_in_time(
    highs: np.ndarray, lows: np.ndarray, current_idx: int, window: int = 3
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Detect confirmed fractal pivot highs and pivot lows up to current_idx.
    A pivot at bar `p` requires window bars on each side: [p-window, p+window].
    Therefore, at bar `current_idx`, only pivots where `p <= current_idx - window`
    have closed and are confirmed. (NO LOOKAHEAD).

    Returns:
      (swing_highs, swing_lows)
      Each item: {"idx": int, "price": float}
    """
    swing_highs = []
    swing_lows = []

    # Maximum pivot index that can be confirmed by current_idx
    max_p = current_idx - window
    min_p = window

    if max_p < min_p:
        return swing_highs, swing_lows

    for p in range(min_p, max_p + 1):
        # High pivot check
        val_h = highs[p]
        is_pivot_h = True
        for offset in range(-window, window + 1):
            if offset == 0:
                continue
            if offset < 0 and highs[p + offset] > val_h:
                is_pivot_h = False
                break
            elif offset > 0 and highs[p + offset] >= val_h:
                is_pivot_h = False
                break
        if is_pivot_h:
            swing_highs.append({"idx": p, "price": float(val_h)})

        # Low pivot check
        val_l = lows[p]
        is_pivot_l = True
        for offset in range(-window, window + 1):
            if offset == 0:
                continue
            if offset < 0 and lows[p + offset] < val_l:
                is_pivot_l = False
                break
            elif offset > 0 and lows[p + offset] <= val_l:
                is_pivot_l = False
                break
        if is_pivot_l:
            swing_lows.append({"idx": p, "price": float(val_l)})

    return swing_highs, swing_lows


def cluster_pivots_into_zones(
    pivots: List[Dict[str, Any]],
    current_idx: int,
    atr_val: float,
    tolerance_atr: float = 1.0,
) -> List[Dict[str, Any]]:
    """
    Cluster pivots that lie within tolerance_atr * atr_val of each other.
    Scores each zone by touch count and recency:
      recency_weight = 1.0 / (1.0 + 0.03 * (current_idx - pivot_idx))
      score = sum(recency_weight)
    """
    if not pivots:
        return []

    tolerance = max(tolerance_atr * atr_val, 0.01)
    # Sort pivots by price
    sorted_pivots = sorted(pivots, key=lambda x: x["price"])

    clusters: List[List[Dict[str, Any]]] = []
    current_cluster: List[Dict[str, Any]] = [sorted_pivots[0]]

    for p in sorted_pivots[1:]:
        # If within tolerance of the cluster average, append
        cluster_prices = [item["price"] for item in current_cluster]
        cluster_mean = sum(cluster_prices) / len(cluster_prices)
        if abs(p["price"] - cluster_mean) <= tolerance:
            current_cluster.append(p)
        else:
            clusters.append(current_cluster)
            current_cluster = [p]
    if current_cluster:
        clusters.append(current_cluster)

    zones = []
    for cl in clusters:
        prices = [x["price"] for x in cl]
        min_p = min(prices)
        max_p = max(prices)
        mid_p = sum(prices) / len(prices)
        touches = len(cl)

        # Recency score
        score = sum(1.0 / (1.0 + 0.03 * max(0, current_idx - x["idx"])) for x in cl)
        zones.append(
            {
                "low": round(min_p, 2),
                "high": round(max_p, 2),
                "mid": round(mid_p, 2),
                "touches": touches,
                "score": round(score, 3),
                "pivots": cl,
            }
        )

    return zones


def get_round_numbers(price: float) -> Tuple[float, float]:
    """
    Compute nearest round number psychological support and resistance
    appropriate for Indian equity price ranges.
    """
    if price <= 0:
        return 0.0, 0.0
    if price < 50:
        step = 5.0
    elif price < 200:
        step = 10.0
    elif price < 1000:
        step = 50.0
    elif price < 5000:
        step = 100.0
    elif price < 20000:
        step = 500.0
    else:
        step = 1000.0

    lower_round = math.floor(price / step) * step
    upper_round = math.ceil(price / step) * step
    if lower_round == price:
        lower_round -= step
    if upper_round == price:
        upper_round += step

    return round(lower_round, 2), round(upper_round, 2)


# ─────────────────────────────────────────────────────────────────────────────
# 3. DIVERGENCE DETECTION (MOMENTUM & PRICE PIVOTS)
# ─────────────────────────────────────────────────────────────────────────────

def detect_rsi_divergence(
    swing_highs: List[Dict[str, Any]],
    swing_lows: List[Dict[str, Any]],
    rsi_series: np.ndarray,
    current_idx: int,
    max_lookback_bars: int = 60,
) -> Optional[Dict[str, Any]]:
    """
    Detect regular bullish or bearish RSI divergence using the last 2 confirmed pivots.
    Regular Bullish: Price lower low, RSI higher low.
    Regular Bearish: Price higher high, RSI lower high.

    Returns dict with divergence type and pivot coordinates for charting, or None.
    """
    # Filter pivots within lookback window
    recent_lows = [p for p in swing_lows if (current_idx - p["idx"]) <= max_lookback_bars]
    recent_highs = [p for p in swing_highs if (current_idx - p["idx"]) <= max_lookback_bars]

    # Check Bullish Divergence first (on lows)
    if len(recent_lows) >= 2:
        p1, p2 = recent_lows[-2], recent_lows[-1]
        price1, price2 = p1["price"], p2["price"]
        rsi1 = float(rsi_series[p1["idx"]])
        rsi2 = float(rsi_series[p2["idx"]])

        # Price makes lower low, RSI makes higher low
        if price2 < price1 and rsi2 > rsi1 + 1.5:
            return {
                "type": "bullish",
                "price_pivots": [
                    {"idx": p1["idx"], "price": price1},
                    {"idx": p2["idx"], "price": price2},
                ],
                "rsi_pivots": [
                    {"idx": p1["idx"], "rsi": round(rsi1, 2)},
                    {"idx": p2["idx"], "rsi": round(rsi2, 2)},
                ],
                "description": f"Regular Bullish Divergence: Price Lower Low ({price1:.2f} -> {price2:.2f}), RSI Higher Low ({rsi1:.1f} -> {rsi2:.1f})",
            }

    # Check Bearish Divergence (on highs)
    if len(recent_highs) >= 2:
        p1, p2 = recent_highs[-2], recent_highs[-1]
        price1, price2 = p1["price"], p2["price"]
        rsi1 = float(rsi_series[p1["idx"]])
        rsi2 = float(rsi_series[p2["idx"]])

        # Price makes higher high, RSI makes lower high
        if price2 > price1 and rsi2 < rsi1 - 1.5:
            return {
                "type": "bearish",
                "price_pivots": [
                    {"idx": p1["idx"], "price": price1},
                    {"idx": p2["idx"], "price": price2},
                ],
                "rsi_pivots": [
                    {"idx": p1["idx"], "rsi": round(rsi1, 2)},
                    {"idx": p2["idx"], "rsi": round(rsi2, 2)},
                ],
                "description": f"Regular Bearish Divergence: Price Higher High ({price1:.2f} -> {price2:.2f}), RSI Lower High ({rsi1:.1f} -> {rsi2:.1f})",
            }

    return None


# ─────────────────────────────────────────────────────────────────────────────
# 4. DETERMINISTIC FEATURE ENGINE (FULL VECTORIZED POINT-IN-TIME PIPELINE)
# ─────────────────────────────────────────────────────────────────────────────

def compute_technical_features(
    df: pd.DataFrame,
    timeframe: str = "1d",
    fractal_window: int = 3,
) -> pd.DataFrame:
    """
    Compute comprehensive technical features across every row of an OHLCV dataframe.
    Point-in-time guarantee: Row t only uses data at or prior to row t.
    """
    if df.empty or len(df) < 5:
        raise ValueError(f"DataFrame has insufficient bars ({len(df)}) for technical analysis.")

    # Standardize column names to lower case
    data = df.copy()
    data.columns = [c.lower() for c in data.columns]
    for req in ["open", "high", "low", "close", "volume"]:
        if req not in data.columns:
            raise ValueError(f"Missing required OHLCV column: '{req}'")

    c = data["close"]
    h = data["high"]
    l = data["low"]
    v = data["volume"]

    # ── 1. TREND FEATURES ──────────────────────────────────────────────────
    atr = compute_atr(h, l, c, period=14)
    data["atr14"] = atr

    ema20 = compute_ema(c, span=20)
    ema50 = compute_ema(c, span=50)
    ema200 = compute_ema(c, span=200)
    data["ema20"] = ema20
    data["ema50"] = ema50
    data["ema200"] = ema200

    # Slopes: change over 5 bars normalized by ATR (slope in ATR units per bar)
    atr_safe = atr.replace(0.0, np.nan)
    data["slope_ema20"] = (ema20 - ema20.shift(5)) / (5.0 * atr_safe)
    data["slope_ema50"] = (ema50 - ema50.shift(5)) / (5.0 * atr_safe)
    data["slope_ema200"] = (ema200 - ema200.shift(5)) / (5.0 * atr_safe)

    # Distances to EMAs in ATR units
    data["dist_ema20_atr"] = (c - ema20) / atr_safe
    data["dist_ema50_atr"] = (c - ema50) / atr_safe
    data["dist_ema200_atr"] = (c - ema200) / atr_safe

    # EMA50 vs EMA200 State (1 = Bullish, -1 = Bearish, 0 = Undetermined)
    has_200 = len(c) >= 50
    data["ema50_above_ema200"] = np.where(
        data["ema200"].notna(), np.where(ema50 >= ema200, 1, -1), 0
    )

    # Bars since golden / death cross
    cross_golden = (ema50 > ema200) & (ema50.shift(1) <= ema200.shift(1))
    cross_death = (ema50 < ema200) & (ema50.shift(1) >= ema200.shift(1))

    bars_since_golden = []
    bars_since_death = []
    last_g = -1
    last_d = -1
    for i in range(len(data)):
        if cross_golden.iloc[i]:
            last_g = i
        if cross_death.iloc[i]:
            last_d = i
        bars_since_golden.append(i - last_g if last_g != -1 else 9999)
        bars_since_death.append(i - last_d if last_d != -1 else 9999)

    data["bars_since_golden_cross"] = bars_since_golden
    data["bars_since_death_cross"] = bars_since_death
    data["last_cross_type"] = np.where(
        np.array(bars_since_golden) < np.array(bars_since_death),
        "golden",
        np.where(np.array(bars_since_death) < np.array(bars_since_golden), "death", "none"),
    )

    # Higher Highs / Higher Lows count over last 10 bars
    hh_series = (h > h.shift(1)).astype(int).rolling(10, min_periods=1).sum()
    hl_series = (l > l.shift(1)).astype(int).rolling(10, min_periods=1).sum()
    lh_series = (h < h.shift(1)).astype(int).rolling(10, min_periods=1).sum()
    ll_series = (l < l.shift(1)).astype(int).rolling(10, min_periods=1).sum()
    data["higher_highs_count_10"] = hh_series
    data["higher_lows_count_10"] = hl_series
    data["lower_highs_count_10"] = lh_series
    data["lower_lows_count_10"] = ll_series

    # ADX(14)
    adx14, plus_di, minus_di = compute_adx(h, l, c, period=14)
    data["adx14"] = adx14
    data["plus_di"] = plus_di
    data["minus_di"] = minus_di

    # ── 2. MOMENTUM FEATURES ───────────────────────────────────────────────
    rsi14 = compute_rsi(c, period=14)
    data["rsi14"] = rsi14
    data["rsi_slope_5"] = (rsi14 - rsi14.shift(5)) / 5.0

    # Regime-aware overbought/oversold boundaries:
    # In Bull regime (Price > EMA200 or EMA50 > EMA200): Bull range is 40-80
    # In Bear regime (Price < EMA200 or EMA50 < EMA200): Bear range is 20-60
    # Otherwise: 30-70
    regimes = []
    is_ob = []
    is_os = []
    for i in range(len(data)):
        p_val = c.iloc[i]
        e200_val = ema200.iloc[i]
        e50_val = ema50.iloc[i]
        r_val = rsi14.iloc[i]

        if not pd.isna(e200_val):
            bull = (p_val >= e200_val) or (e50_val >= e200_val)
            bear = (p_val < e200_val) and (e50_val < e200_val)
        else:
            bull = p_val >= e50_val
            bear = p_val < e50_val

        if bull:
            reg = "bull_regime"
            ob = r_val >= 80.0
            os = r_val <= 40.0
        elif bear:
            reg = "bear_regime"
            ob = r_val >= 60.0
            os = r_val <= 20.0
        else:
            reg = "neutral_regime"
            ob = r_val >= 70.0
            os = r_val <= 30.0

        regimes.append(reg)
        is_ob.append(ob)
        is_os.append(os)

    data["regime"] = regimes
    data["rsi_overbought"] = is_ob
    data["rsi_oversold"] = is_os

    # MACD(12, 26, 9)
    macd_line, macd_sig, macd_hist = compute_macd(c)
    data["macd"] = macd_line
    data["macd_signal"] = macd_sig
    data["macd_hist"] = macd_hist

    # ROC(14) Rate of Change
    data["roc14"] = ((c - c.shift(14)) / c.shift(14).replace(0.0, np.nan)) * 100.0

    # ── 3. VOLUME FEATURES ─────────────────────────────────────────────────
    vol_mean20 = v.rolling(20, min_periods=1).mean().replace(0.0, np.nan)
    data["rvol20"] = v / vol_mean20

    # On-Balance Volume (OBV)
    direction_sign = np.sign(c.diff()).fillna(0.0)
    obv_step = direction_sign * v
    obv = obv_step.cumsum()
    data["obv"] = obv
    data["obv_slope_5"] = (obv - obv.shift(5)) / 5.0

    # Volume on Up bars vs Down bars over last 20 bars
    up_bars = c > c.shift(1)
    down_bars = c < c.shift(1)
    up_vol = (v * up_bars.astype(int)).rolling(20, min_periods=1).sum()
    down_vol = (v * down_bars.astype(int)).rolling(20, min_periods=1).sum().replace(0.0, 1.0)
    data["up_down_volume_ratio"] = up_vol / down_vol

    # Climax and Dry-up flags
    data["vol_climax"] = data["rvol20"] >= 2.5
    data["vol_dryup"] = data["rvol20"] <= 0.5

    # Volume confirm / diverge flag:
    # Price move over 5 bars vs OBV move over 5 bars
    price_change_5 = c - c.shift(5)
    obv_change_5 = obv - obv.shift(5)
    confirm_flags = []
    for p_ch, o_ch in zip(price_change_5, obv_change_5):
        if pd.isna(p_ch) or pd.isna(o_ch):
            confirm_flags.append("neutral")
        elif p_ch > 0 and o_ch > 0:
            confirm_flags.append("confirms")  # Bullish confirmation
        elif p_ch < 0 and o_ch < 0:
            confirm_flags.append("confirms")  # Bearish confirmation
        elif (p_ch > 0 and o_ch < 0) or (p_ch < 0 and o_ch > 0):
            confirm_flags.append("diverges")  # Volume divergence
        else:
            confirm_flags.append("neutral")
    data["volume_confirmation"] = confirm_flags

    # ── 4. BOLLINGER BANDWIDTH & PHASE CLASSIFICATION ─────────────────────
    _, _, _, bbw = compute_bollinger_bands(c, period=20, num_std=2.0)
    data["bollinger_bandwidth"] = bbw

    # Bollinger Bandwidth percentile over last 50 bars
    bbw_pct = bbw.rolling(50, min_periods=10).apply(
        lambda s: (s < s.iloc[-1]).mean() * 100.0 if len(s) > 0 else 50.0, raw=False
    ).fillna(50.0)
    data["bbw_percentile"] = bbw_pct

    # Phase rules: accumulation, markup, distribution, markdown
    phases = []
    phase_rules = []
    for i in range(len(data)):
        price_i = c.iloc[i]
        e200_i = ema200.iloc[i] if not pd.isna(ema200.iloc[i]) else ema50.iloc[i]
        slope50_i = data["slope_ema50"].iloc[i]
        dist200_atr_i = (
            data["dist_ema200_atr"].iloc[i] if not pd.isna(data["dist_ema200_atr"].iloc[i]) else 0.0
        )
        pct_bw = bbw_pct.iloc[i]
        r_val = rsi14.iloc[i]
        vol_conf = data["volume_confirmation"].iloc[i]

        # Rule evaluation in deterministic hierarchy:
        if pct_bw <= 30.0 and abs(dist200_atr_i) <= 2.5 and abs(slope50_i) < 0.20:
            phases.append("accumulation")
            phase_rules.append(
                f"Accumulation: Volatility compression (BBW rank {pct_bw:.1f}%) near baseline EMA with flat slope ({slope50_i:+.2f} ATR/bar)"
            )
        elif price_i >= e200_i and slope50_i > 0.05 and price_i >= ema50.iloc[i]:
            phases.append("markup")
            phase_rules.append(
                f"Markup: Price above EMA200 with positive EMA50 slope ({slope50_i:+.2f} ATR/bar) and price expansion"
            )
        elif price_i >= e200_i and (slope50_i <= 0.0 or (r_val > 65.0 and vol_conf == "diverges")):
            phases.append("distribution")
            phase_rules.append(
                f"Distribution: Price elevated above EMA200 but momentum stalling with weakening slope ({slope50_i:+.2f} ATR/bar) or volume divergence"
            )
        elif price_i < e200_i and slope50_i < -0.05 and price_i < ema50.iloc[i]:
            phases.append("markdown")
            phase_rules.append(
                f"Markdown: Price below EMA200 with negative EMA50 slope ({slope50_i:+.2f} ATR/bar)"
            )
        else:
            # Fallback based on prevailing EMA alignment
            if price_i >= e200_i:
                phases.append("markup" if slope50_i >= 0 else "distribution")
                phase_rules.append(
                    f"Consolidation/Markup: Price above EMA200, slope {slope50_i:+.2f} ATR/bar"
                )
            else:
                phases.append("markdown" if slope50_i < 0 else "accumulation")
                phase_rules.append(
                    f"Consolidation/Markdown: Price below EMA200, slope {slope50_i:+.2f} ATR/bar"
                )

    data["phase"] = phases
    data["phase_rule"] = phase_rules

    # ── 5. LEVELS (52-WEEK HIGH/LOW, ROUND NUMBERS, PIVOT DISTANCES) ───────
    # 52-week rolling window: 252 bars for 1d, 1200 for 1h, etc.
    lookback_52w = 252 if timeframe in ("1d", "1wk") else min(len(data), 500)
    high_52w = h.rolling(lookback_52w, min_periods=1).max()
    low_52w = l.rolling(lookback_52w, min_periods=1).min()
    data["high_52w"] = high_52w
    data["low_52w"] = low_52w
    data["range_position_pct"] = (
        ((c - low_52w) / (high_52w - low_52w).replace(0.0, np.nan)) * 100.0
    ).fillna(50.0)

    # Convert to numpy for fast pivot analysis
    highs_arr = h.to_numpy()
    lows_arr = l.to_numpy()
    close_arr = c.to_numpy()
    atr_arr = atr.to_numpy()
    rsi_arr = rsi14.to_numpy()

    nearest_support_mid = []
    nearest_support_dist_pct = []
    nearest_support_dist_atr = []
    nearest_resistance_mid = []
    nearest_resistance_dist_pct = []
    nearest_resistance_dist_atr = []
    approaching_sup = []
    approaching_res = []

    # Vector calculation for levels at each bar
    for idx in range(len(data)):
        cur_p = close_arr[idx]
        cur_atr = atr_arr[idx] if not np.isnan(atr_arr[idx]) and atr_arr[idx] > 0 else cur_p * 0.015

        # Strictly point-in-time confirmed pivots
        s_highs, s_lows = find_fractal_pivots_point_in_time(
            highs_arr, lows_arr, current_idx=idx, window=fractal_window
        )

        sup_zones = cluster_pivots_into_zones(s_lows, current_idx=idx, atr_val=cur_atr)
        res_zones = cluster_pivots_into_zones(s_highs, current_idx=idx, atr_val=cur_atr)

        # Supports below current price
        valid_supports = [z for z in sup_zones if z["mid"] < cur_p * 0.999]
        # Resistances above current price
        valid_resistances = [z for z in res_zones if z["mid"] > cur_p * 1.001]

        if valid_supports:
            best_sup = max(valid_supports, key=lambda z: z["mid"])
            s_mid = best_sup["mid"]
        else:
            # Fallback: 52w low or round number
            s_mid = low_52w.iloc[idx] if low_52w.iloc[idx] < cur_p else round(cur_p * 0.95, 2)

        if valid_resistances:
            best_res = min(valid_resistances, key=lambda z: z["mid"])
            r_mid = best_res["mid"]
        else:
            # Fallback: 52w high or round number
            r_mid = high_52w.iloc[idx] if high_52w.iloc[idx] > cur_p else round(cur_p * 1.05, 2)

        d_sup_pct = round(((cur_p - s_mid) / cur_p) * 100.0, 2)
        d_sup_atr = round((cur_p - s_mid) / cur_atr, 2)
        d_res_pct = round(((r_mid - cur_p) / cur_p) * 100.0, 2)
        d_res_atr = round((r_mid - cur_p) / cur_atr, 2)

        nearest_support_mid.append(s_mid)
        nearest_support_dist_pct.append(d_sup_pct)
        nearest_support_dist_atr.append(d_sup_atr)
        nearest_resistance_mid.append(r_mid)
        nearest_resistance_dist_pct.append(d_res_pct)
        nearest_resistance_dist_atr.append(d_res_atr)

        approaching_sup.append(d_sup_atr <= 1.0)
        approaching_res.append(d_res_atr <= 1.0)

    data["nearest_support_mid"] = nearest_support_mid
    data["dist_to_support_pct"] = nearest_support_dist_pct
    data["dist_to_support_atr"] = nearest_support_dist_atr
    data["nearest_resistance_mid"] = nearest_resistance_mid
    data["dist_to_resistance_pct"] = nearest_resistance_dist_pct
    data["dist_to_resistance_atr"] = nearest_resistance_dist_atr
    data["approaching_support"] = approaching_sup
    data["approaching_resistance"] = approaching_res

    # Fill any remaining NaNs safely
    data = data.ffill().bfill()
    return data


# ─────────────────────────────────────────────────────────────────────────────
# 5. DETAILED SNAPSHOT / SUMMARY (FOR THE LATEST BAR / API OUTPUT)
# ─────────────────────────────────────────────────────────────────────────────

def get_latest_technical_summary(
    df: pd.DataFrame,
    timeframe: str = "1d",
    fractal_window: int = 3,
) -> Dict[str, Any]:
    """
    Produce the full structured technical analysis for the most recent bar.
    Includes rich nested objects for levels, momentum divergence, volume, and phase.
    """
    featured_df = compute_technical_features(df, timeframe=timeframe, fractal_window=fractal_window)
    last_idx = len(featured_df) - 1
    last_row = featured_df.iloc[-1]

    highs_arr = featured_df["high"].to_numpy()
    lows_arr = featured_df["low"].to_numpy()
    atr_val = float(last_row["atr14"])
    cur_p = float(last_row["close"])

    # 1. Swing High/Low Pivots and Clustered Zones
    s_highs, s_lows = find_fractal_pivots_point_in_time(
        highs_arr, lows_arr, current_idx=last_idx, window=fractal_window
    )
    sup_zones = cluster_pivots_into_zones(s_lows, current_idx=last_idx, atr_val=atr_val)
    res_zones = cluster_pivots_into_zones(s_highs, current_idx=last_idx, atr_val=atr_val)

    # Sort supports by price desc, resistances by price asc
    supports_below = sorted([z for z in sup_zones if z["mid"] < cur_p * 0.999], key=lambda x: -x["mid"])
    resistances_above = sorted([z for z in res_zones if z["mid"] > cur_p * 1.001], key=lambda x: x["mid"])

    round_sup, round_res = get_round_numbers(cur_p)

    # 2. RSI Divergence
    rsi_arr = featured_df["rsi14"].to_numpy()
    divergence = detect_rsi_divergence(
        swing_highs=s_highs,
        swing_lows=s_lows,
        rsi_series=rsi_arr,
        current_idx=last_idx,
    )

    # Approaching status
    approaching = "none"
    if bool(last_row["approaching_support"]):
        approaching = "support"
    elif bool(last_row["approaching_resistance"]):
        approaching = "resistance"

    return {
        "as_of_index": int(last_idx),
        "as_of_time": str(featured_df.index[-1]),
        "timeframe": timeframe,
        "current_price": cur_p,
        "trend": {
            "state": (
                "STRONG_UPTREND"
                if cur_p > last_row["ema20"] > last_row["ema50"] and last_row["rsi14"] > 55
                else "UPTREND"
                if cur_p > last_row["ema50"]
                else "STRONG_DOWNTREND"
                if cur_p < last_row["ema20"] < last_row["ema50"] and last_row["rsi14"] < 45
                else "DOWNTREND"
                if cur_p < last_row["ema50"]
                else "SIDEWAYS"
            ),
            "phase": str(last_row["phase"]),
            "rule_fired": str(last_row["phase_rule"]),
            "ema20": round(float(last_row["ema20"]), 2),
            "ema50": round(float(last_row["ema50"]), 2),
            "ema200": round(float(last_row["ema200"]), 2) if not pd.isna(last_row["ema200"]) else None,
            "dist_ema20_atr": round(float(last_row["dist_ema20_atr"]), 2),
            "dist_ema50_atr": round(float(last_row["dist_ema50_atr"]), 2),
            "dist_ema200_atr": round(float(last_row["dist_ema200_atr"]), 2) if not pd.isna(last_row["dist_ema200_atr"]) else None,
            "slope_ema50": round(float(last_row["slope_ema50"]), 3),
            "adx14": round(float(last_row["adx14"]), 1),
            "higher_highs_count": int(last_row["higher_highs_count_10"]),
            "higher_lows_count": int(last_row["higher_lows_count_10"]),
            "bars_since_golden_cross": int(last_row["bars_since_golden_cross"]),
            "bars_since_death_cross": int(last_row["bars_since_death_cross"]),
            "last_cross_type": str(last_row["last_cross_type"]),
        },
        "levels": {
            "supports": [
                {"low": z["low"], "high": z["high"], "mid": z["mid"], "touches": z["touches"], "score": z["score"]}
                for z in supports_below[:3]
            ],
            "resistances": [
                {"low": z["low"], "high": z["high"], "mid": z["mid"], "touches": z["touches"], "score": z["score"]}
                for z in resistances_above[:3]
            ],
            "nearest_support": float(last_row["nearest_support_mid"]),
            "nearest_resistance": float(last_row["nearest_resistance_mid"]),
            "dist_to_support_pct": float(last_row["dist_to_support_pct"]),
            "dist_to_support_atr": float(last_row["dist_to_support_atr"]),
            "dist_to_resistance_pct": float(last_row["dist_to_resistance_pct"]),
            "dist_to_resistance_atr": float(last_row["dist_to_resistance_atr"]),
            "approaching": approaching,
            "high_52w": round(float(last_row["high_52w"]), 2),
            "low_52w": round(float(last_row["low_52w"]), 2),
            "round_number_support": round_sup,
            "round_number_resistance": round_res,
        },
        "momentum": {
            "rsi": round(float(last_row["rsi14"]), 1),
            "rsi_slope": round(float(last_row["rsi_slope_5"]), 2),
            "regime": str(last_row["regime"]),
            "is_overbought": bool(last_row["rsi_overbought"]),
            "is_oversold": bool(last_row["rsi_oversold"]),
            "macd": round(float(last_row["macd"]), 2),
            "macd_signal": round(float(last_row["macd_signal"]), 2),
            "macd_hist": round(float(last_row["macd_hist"]), 2),
            "roc14": round(float(last_row["roc14"]), 2),
            "divergence": divergence,
        },
        "volume": {
            "rvol20": round(float(last_row["rvol20"]), 2),
            "obv_slope": round(float(last_row["obv_slope_5"]), 2),
            "up_down_ratio": round(float(last_row["up_down_volume_ratio"]), 2),
            "climax": bool(last_row["vol_climax"]),
            "dryup": bool(last_row["vol_dryup"]),
            "confirmation": str(last_row["volume_confirmation"]),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 6. MULTI-TIMEFRAME ALIGNMENT (POINT-IN-TIME / NO LOOKAHEAD)
# ─────────────────────────────────────────────────────────────────────────────

def compute_multi_timeframe_alignment(
    timeframe_dfs: Dict[str, pd.DataFrame],
    eval_timestamp: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Computes trend state across timeframes (1h, 1d, 1wk) point-in-time.
    Rules:
    - For evaluation at eval_timestamp (or latest lower-timeframe bar),
      higher timeframe bars MUST be strictly CLOSED prior to eval_timestamp.
    - No partial / in-progress daily or weekly candle may be used.

    Returns:
      {
        "alignment_score": float between -1.0 and +1.0,
        "alignment_state": "strongly_bullish" | "bullish" | "mixed" | "bearish" | "strongly_bearish",
        "timeframe_states": {"1h": 1, "1d": 1, "1wk": 0, ...},
        "weights": {"1h": 0.25, "1d": 0.45, "1wk": 0.30}
      }
    """
    weights = {"1h": 0.25, "1d": 0.45, "1wk": 0.30}
    tf_scores: Dict[str, int] = {}

    for tf in ["1h", "1d", "1wk"]:
        if tf not in timeframe_dfs or timeframe_dfs[tf].empty:
            continue
        df = timeframe_dfs[tf]

        # Filter strictly closed bars prior to or at eval_timestamp
        if eval_timestamp is not None:
            # If datetime index
            if isinstance(df.index, pd.DatetimeIndex):
                eval_dt = pd.to_datetime(eval_timestamp)
                # If evaluating intraday, daily bar of the same day is NOT closed yet!
                if tf == "1d":
                    closed_df = df[df.index < eval_dt.floor("D")]
                elif tf == "1wk":
                    # Weekly bar closes at end of week
                    closed_df = df[df.index < (eval_dt - pd.Timedelta(days=eval_dt.weekday())).floor("D")]
                else:
                    closed_df = df[df.index <= eval_dt]
            else:
                closed_df = df
        else:
            closed_df = df

        if len(closed_df) < 5:
            tf_scores[tf] = 0
            continue

        c = closed_df["close"].iloc[-1]
        ema20 = float(compute_ema(closed_df["close"], 20).iloc[-1])
        ema50 = float(compute_ema(closed_df["close"], 50).iloc[-1])
        rsi = float(compute_rsi(closed_df["close"], 14).iloc[-1])

        # Direction: +1 (Bullish), -1 (Bearish), 0 (Neutral)
        if c > ema20 > ema50 and rsi > 50:
            tf_scores[tf] = 1
        elif c < ema20 < ema50 and rsi < 50:
            tf_scores[tf] = -1
        elif c > ema50:
            tf_scores[tf] = 1
        elif c < ema50:
            tf_scores[tf] = -1
        else:
            tf_scores[tf] = 0

    # Calculate weighted composite score
    total_w = sum(weights[tf] for tf in tf_scores if tf in weights)
    if total_w > 0:
        composite = sum(tf_scores[tf] * weights[tf] for tf in tf_scores if tf in weights) / total_w
    else:
        composite = 0.0

    composite = round(composite, 2)
    if composite >= 0.6:
        state = "strongly_bullish"
    elif composite > 0.2:
        state = "bullish"
    elif composite <= -0.6:
        state = "strongly_bearish"
    elif composite < -0.2:
        state = "bearish"
    else:
        state = "mixed"

    return {
        "alignment_score": composite,
        "alignment_state": state,
        "timeframe_states": tf_scores,
        "weights": {tf: weights[tf] for tf in tf_scores if tf in weights},
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7. CANDLE FETCHER & YFINANCE LIMIT REPORTING
# ─────────────────────────────────────────────────────────────────────────────

# Expected max history by timeframe according to yfinance API boundaries
YFINANCE_TIMEFRAME_LIMITS = {
    "15m": {"max_days": 60, "recommended_period": "59d"},
    "1h": {"max_days": 730, "recommended_period": "720d"},
    "1d": {"max_days": 3650, "recommended_period": "5y"},
    "1wk": {"max_days": 7300, "recommended_period": "10y"},
}

def fetch_timeframe_candles(
    ticker: str,
    timeframe: str = "1d",
    period: Optional[str] = None,
    yf_client: Optional[Any] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Fetch OHLCV candles from yfinance respecting intraday limits.
    Reports data quality, bar count, start/end dates, and explicit warnings
    about limited intraday sample size.
    """
    clean_ticker = ticker.strip().upper()
    tf_meta = YFINANCE_TIMEFRAME_LIMITS.get(timeframe, {"max_days": 365, "recommended_period": "1y"})
    use_period = period or tf_meta["recommended_period"]

    data_quality: Dict[str, Any] = {
        "ticker": clean_ticker,
        "timeframe": timeframe,
        "period_requested": use_period,
        "bars_count": 0,
        "start_date": None,
        "end_date": None,
        "sample_size_limited": timeframe in ("15m", "1h"),
        "warnings": [],
    }

    if timeframe == "15m":
        data_quality["warnings"].append(
            "15m intraday history limited to ~60 calendar days by yfinance API boundaries."
        )
    elif timeframe == "1h":
        data_quality["warnings"].append(
            "1h intraday history limited to ~730 calendar days (2 years) by yfinance API boundaries."
        )

    try:
        import yfinance as yf
        client = yf_client or yf
        t_obj = client.Ticker(clean_ticker)
        df = t_obj.history(period=use_period, interval=timeframe, auto_adjust=False)
    except Exception as e:
        logger.error(f"yfinance fetch error for {clean_ticker} [{timeframe}]: {e}")
        data_quality["warnings"].append(f"yfinance fetch failed: {str(e)}")
        return pd.DataFrame(), data_quality

    if df is None or df.empty:
        data_quality["warnings"].append("No candle data returned for ticker.")
        return pd.DataFrame(), data_quality

    # Normalize columns
    df.columns = [c.lower() for c in df.columns]
    keep_cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[keep_cols].dropna()

    data_quality["bars_count"] = len(df)
    if not df.empty:
        data_quality["start_date"] = str(df.index[0])
        data_quality["end_date"] = str(df.index[-1])

    if len(df) < 50:
        data_quality["warnings"].append(
            f"Small sample size ({len(df)} bars). Some long indicators (EMA200) may be unavailable."
        )

    return df, data_quality
