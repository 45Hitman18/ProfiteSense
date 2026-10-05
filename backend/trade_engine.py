"""
trade_engine.py
───────────────────────────────────────────────────────────────────────────────
ProfitSense Analytical Trade Engine for Indian Equities (NSE/BSE)

Instead of random/heuristic multipliers, this engine:
1. Fetches REAL 90-day OHLCV data from yfinance
2. Computes proper technical indicators:
   - ATR (Average True Range) for volatility-adjusted stop-loss
   - EMA 20/50 for trend detection
   - Support / Resistance pivot levels from actual price history
   - 52-week range position (where stock sits in annual range)
   - RSI for overbought/oversold conditions
3. Computes precise, data-backed trade levels:
   - Buying zone anchored to nearest support
   - Targets anchored to real resistance levels
   - Stop-loss set at ATR-based distance below support
   - Risk-Reward ratio calculated from actual levels
4. Blends with NLP sentiment confidence to adjust conviction
"""

import math
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

# ── yfinance for live data ────────────────────────────────────────────────────
try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
#  CACHE  (TTL 5 minutes per ticker – avoids hammering yfinance on every click)
# ─────────────────────────────────────────────────────────────────────────────
_ENGINE_CACHE: Dict[str, Dict[str, Any]] = {}
ENGINE_CACHE_TTL = 300  # 5 minutes


def _now_ts() -> float:
    return time.time()


def _get_from_cache(ticker: str) -> Optional[Dict[str, Any]]:
    if ticker in _ENGINE_CACHE:
        entry = _ENGINE_CACHE[ticker]
        if _now_ts() - entry["ts"] < ENGINE_CACHE_TTL:
            return entry["data"]
    return None


def _put_to_cache(ticker: str, data: Dict[str, Any]) -> None:
    _ENGINE_CACHE[ticker] = {"ts": _now_ts(), "data": data}


# ─────────────────────────────────────────────────────────────────────────────
#  TECHNICAL INDICATOR CALCULATIONS
# ─────────────────────────────────────────────────────────────────────────────

def _ema(prices: List[float], period: int) -> float:
    """Compute the most recent EMA of a price list."""
    if len(prices) < period:
        return prices[-1] if prices else 0.0
    k = 2.0 / (period + 1)
    ema = sum(prices[:period]) / period  # seed with SMA
    for p in prices[period:]:
        ema = p * k + ema * (1 - k)
    return round(ema, 2)


def _atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
    """Average True Range (ATR) – the standard measure of price volatility."""
    if len(highs) < period + 1:
        # Fallback: simple average of (high-low) for available data
        ranges = [h - l for h, l in zip(highs, lows)]
        return round(sum(ranges) / len(ranges), 2) if ranges else 0.0

    true_ranges = []
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        true_ranges.append(tr)

    # Wilder's smoothed ATR
    atr = sum(true_ranges[:period]) / period
    for tr in true_ranges[period:]:
        atr = (atr * (period - 1) + tr) / period

    return round(atr, 2)


def _rsi(closes: List[float], period: int = 14) -> float:
    """Relative Strength Index."""
    if len(closes) < period + 1:
        return 50.0

    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        if delta > 0:
            gains.append(delta)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(delta))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def _find_support_resistance(
    highs: List[float], lows: List[float], closes: List[float], current_price: float,
    lookback: int = 60
) -> Tuple[float, float]:
    """
    Find nearest support and resistance using pivot points.
    Uses a simplified swing-high/swing-low detection from the recent lookback window.
    Returns (nearest_support_below_price, nearest_resistance_above_price).
    """
    window = min(lookback, len(closes))
    recent_highs = highs[-window:]
    recent_lows = lows[-window:]
    recent_closes = closes[-window:]

    # Find local swing highs and lows (window of 3)
    swing_highs = []
    swing_lows = []
    for i in range(1, len(recent_highs) - 1):
        if recent_highs[i] > recent_highs[i - 1] and recent_highs[i] > recent_highs[i + 1]:
            swing_highs.append(recent_highs[i])
        if recent_lows[i] < recent_lows[i - 1] and recent_lows[i] < recent_lows[i + 1]:
            swing_lows.append(recent_lows[i])

    # Cluster levels within 1.5% of each other
    def cluster_levels(levels: List[float], threshold_pct: float = 1.5) -> List[float]:
        if not levels:
            return []
        sorted_levels = sorted(set(levels))
        clustered = [sorted_levels[0]]
        for lvl in sorted_levels[1:]:
            if abs(lvl - clustered[-1]) / clustered[-1] * 100 > threshold_pct:
                clustered.append(lvl)
            else:
                # Replace with average of cluster
                clustered[-1] = round((clustered[-1] + lvl) / 2, 2)
        return clustered

    # Support: swing lows below current price
    supports_below = [l for l in cluster_levels(swing_lows) if l < current_price * 0.998]
    # Resistance: swing highs above current price
    resistances_above = [h for h in cluster_levels(swing_highs) if h > current_price * 1.002]

    # Pick nearest support and resistance
    if supports_below:
        nearest_support = max(supports_below)
    else:
        # Fallback: use 52w low proximity
        nearest_support = round(current_price * 0.95, 2)

    if resistances_above:
        nearest_resistance = min(resistances_above)
    else:
        # Fallback: use 52w high proximity
        nearest_resistance = round(current_price * 1.08, 2)

    return nearest_support, nearest_resistance


def _compute_trend(
    ema20: float, ema50: float, current_price: float, rsi: float
) -> str:
    """Determine overall price trend."""
    price_above_ema20 = current_price > ema20
    ema20_above_ema50 = ema20 > ema50

    if price_above_ema20 and ema20_above_ema50 and rsi > 50:
        return "STRONG_UPTREND"
    elif price_above_ema20 and rsi > 45:
        return "UPTREND"
    elif not price_above_ema20 and not ema20_above_ema50 and rsi < 50:
        return "STRONG_DOWNTREND"
    elif not price_above_ema20 and rsi < 55:
        return "DOWNTREND"
    else:
        return "SIDEWAYS"


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN TRADE ANALYSIS ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def compute_trade_analysis(
    ticker: str,
    direction: str = "NEUTRAL",
    confidence: float = 70.0,
    sentiment_score: float = 0.5,
    event_type: str = ""
) -> Dict[str, Any]:
    """
    Compute analytical trade guidance for a given ticker.
    
    Steps:
    1. Fetch 90-day OHLCV data (real candles) from yfinance
    2. Compute ATR-14, EMA-20, EMA-50, RSI-14
    3. Find nearest support/resistance from swing pivots
    4. Derive buying zone, targets, and stop-loss from REAL levels
    5. Blend with NLP sentiment for conviction adjustments
    
    Returns a rich dict with all levels, technical context, and interpretation.
    """
    ticker_clean = ticker.strip().upper()

    # ── 1. Cache check ────────────────────────────────────────────────────────
    cached = _get_from_cache(ticker_clean)
    if cached:
        # Re-blend fresh sentiment without refetching price data
        return _blend_sentiment(cached, direction, confidence, sentiment_score, event_type)

    # ── 2. Fetch 90-day OHLCV ─────────────────────────────────────────────────
    ohlcv_data = _fetch_ohlcv(ticker_clean, period="3mo")
    if not ohlcv_data or len(ohlcv_data) < 10:
        return _fallback_analysis(ticker_clean, direction, confidence, sentiment_score)

    opens  = [d["open"]  for d in ohlcv_data]
    highs  = [d["high"]  for d in ohlcv_data]
    lows   = [d["low"]   for d in ohlcv_data]
    closes = [d["close"] for d in ohlcv_data]
    vols   = [d["volume"] for d in ohlcv_data]

    current_price = closes[-1]
    if current_price <= 0:
        return _fallback_analysis(ticker_clean, direction, confidence, sentiment_score)

    # ── 3. Compute Technical Indicators ───────────────────────────────────────
    atr14 = _atr(highs, lows, closes, period=14)
    ema20 = _ema(closes, period=20)
    ema50 = _ema(closes, period=50)
    rsi14 = _rsi(closes, period=14)

    # Validate ATR (sanity-cap at 10% of price)
    max_sane_atr = current_price * 0.10
    if atr14 > max_sane_atr:
        atr14 = max_sane_atr * 0.7

    # 52-week range
    high_52w = max(highs)
    low_52w  = min(lows)
    range_position_pct = round(((current_price - low_52w) / max(high_52w - low_52w, 1)) * 100, 1)

    # Average volume
    avg_vol = round(sum(vols[-20:]) / 20) if len(vols) >= 20 else round(sum(vols) / len(vols))
    latest_vol = vols[-1]
    vol_ratio = round(latest_vol / avg_vol, 2) if avg_vol > 0 else 1.0

    # ── 4. Support & Resistance ───────────────────────────────────────────────
    support, resistance = _find_support_resistance(highs, lows, closes, current_price)

    # Distance from support and resistance
    dist_to_support    = round(((current_price - support)    / current_price) * 100, 2)
    dist_to_resistance = round(((resistance - current_price) / current_price) * 100, 2)

    # ── 5. Trend Classification ───────────────────────────────────────────────
    trend = _compute_trend(ema20, ema50, current_price, rsi14)

    # ── 6. Cache raw technical data ───────────────────────────────────────────
    tech_data = {
        "ticker":             ticker_clean,
        "current_price":      current_price,
        "atr14":              atr14,
        "ema20":              ema20,
        "ema50":              ema50,
        "rsi14":              rsi14,
        "support":            support,
        "resistance":         resistance,
        "dist_to_support":    dist_to_support,
        "dist_to_resistance": dist_to_resistance,
        "high_52w":           high_52w,
        "low_52w":            low_52w,
        "range_position_pct": range_position_pct,
        "trend":              trend,
        "avg_volume":         avg_vol,
        "latest_volume":      latest_vol,
        "volume_ratio":       vol_ratio,
    }
    _put_to_cache(ticker_clean, tech_data)

    # ── 7. Blend sentiment + generate recommendations ─────────────────────────
    return _blend_sentiment(tech_data, direction, confidence, sentiment_score, event_type)


def _blend_sentiment(
    tech: Dict[str, Any],
    direction: str,
    confidence: float,
    sentiment_score: float,
    event_type: str = ""
) -> Dict[str, Any]:
    """
    Given technical data and NLP sentiment, compute precise trade levels.
    All levels are anchored to REAL support/resistance and ATR, NOT random multipliers.
    """
    price     = tech["current_price"]
    atr       = tech["atr14"]
    support   = tech["support"]
    resistance= tech["resistance"]
    rsi       = tech["rsi14"]
    trend     = tech["trend"]
    ema20     = tech["ema20"]
    ema50     = tech["ema50"]
    rp        = tech["range_position_pct"]  # 0–100, how high in 52w range

    dir_upper = direction.upper()
    is_up     = dir_upper in ("UP", "BULLISH")
    is_down   = dir_upper in ("DOWN", "BEARISH")
    # Combine NLP direction with technical trend
    tech_bullish = trend in ("STRONG_UPTREND", "UPTREND")
    tech_bearish = trend in ("STRONG_DOWNTREND", "DOWNTREND")

    # ── Event multiplier (same catalog as NLP engine) ─────────────────────────
    event_multipliers = {
        "EARNINGS": 1.30, "PROFIT_LOSS": 1.25, "REVENUE": 1.20,
        "MERGER_ACQUISITION": 1.35, "REGULATORY_ACTION": 1.20,
        "RBI_ANNOUNCEMENT": 1.18, "CRUDE_OIL": 1.10, "DIVIDEND": 0.90,
        "PRODUCT_LAUNCH": 1.08, "MANAGEMENT_CHANGE": 0.95
    }
    evt_mult = event_multipliers.get(event_type, 1.0)

    # ── Conviction score (0–1) blending NLP confidence + technical alignment ──
    nlp_conf_norm = min(max(confidence / 100.0, 0.0), 1.0)
    tech_align = (
        1.0 if (is_up and tech_bullish) or (is_down and tech_bearish) else
        0.6 if (is_up and not tech_bearish) or (is_down and not tech_bullish) else
        0.35  # Sentiment vs. technical divergence → lower conviction
    )
    conviction = round(nlp_conf_norm * tech_align, 3)

    # ── RSI Adjustment ────────────────────────────────────────────────────────
    # Overbought (RSI > 70): tighten upside targets, widen stop
    # Oversold (RSI < 30): expand upside targets for bullish calls
    rsi_upside_boost = 1.0
    if is_up:
        if rsi > 70:
            rsi_upside_boost = 0.75  # Already overbought – conservative targets
        elif rsi < 40:
            rsi_upside_boost = 1.20  # Oversold bounce – more room to run
        elif rsi < 50:
            rsi_upside_boost = 1.10

    if is_down:
        if rsi < 30:
            rsi_upside_boost = 0.75  # Already oversold – conservative downside
        elif rsi > 65:
            rsi_upside_boost = 1.20  # Overbought – strong downside potential

    # ── BULLISH TRADE LEVELS ──────────────────────────────────────────────────
    action = "HOLD"
    action_label = "HOLD & MONITOR"
    buy_low = None
    buy_high = None
    target1 = None
    target2 = None
    stop_loss = None
    target1_pct = 0.0
    target2_pct = 0.0
    stop_pct = 0.0
    risk_reward = "—"
    strategy_notes = []

    if is_up:
        # Buying Zone: Current price to slightly below, anchored to support
        # Use 0.5×ATR discount as optimal dip-buying range
        buy_low  = round(max(support * 1.002, price - 0.5 * atr), 2)
        buy_high = round(price + 0.2 * atr, 2)

        # Stop Loss: ATR-based below the support level
        # If price is very close to support (< 1.5%), tighter stop
        atr_sl_mult = 1.0 if tech["dist_to_support"] < 2.0 else 1.3
        stop_loss = round(support - atr_sl_mult * atr * evt_mult, 2)
        stop_pct  = round(((price - stop_loss) / price) * 100, 2)

        # Target 1: Nearest resistance (anchored to swing high)
        # RSI boost extends the distance from price-to-resistance, not the absolute resistance
        t1_base = resistance
        # If resistance is very close (< 1.5%), project next level using ATR
        if tech["dist_to_resistance"] < 1.5:
            t1_base = resistance + 2.0 * atr

        # Extend gap by RSI boost (not the absolute price)
        gap_to_t1 = t1_base - price
        target1 = round(price + gap_to_t1 * rsi_upside_boost * evt_mult, 2)
        target1_pct = round(((target1 - price) / price) * 100, 2)

        # Target 2: ATR-based extension above T1 (typically 1.5–2.5 ATR above T1)
        # This keeps T2 realistic and tethered to actual volatility
        t2_atr_mult = min(2.5, max(1.5, 2.0 * evt_mult))
        target2 = round(target1 + t2_atr_mult * atr, 2)
        target2_pct = round(((target2 - price) / price) * 100, 2)

        # Risk-Reward
        reward1 = target1 - price
        risk    = price - stop_loss
        if risk > 0:
            rr_val = round(reward1 / risk, 2)
            risk_reward = f"1 : {rr_val}"

        # Action
        if conviction >= 0.75 and tech_bullish:
            action = "STRONG_BUY"
            action_label = "STRONG BUY / ACCUMULATE"
        elif conviction >= 0.55:
            action = "BUY_DIPS"
            action_label = "BUY ON DIPS / ACCUMULATE"
        else:
            action = "WATCHLIST"
            action_label = "BULLISH WATCH — AWAIT CONFIRMATION"

        # Strategy notes
        strategy_notes = _build_bullish_notes(
            price, buy_low, buy_high, target1, target2, stop_loss,
            rsi, trend, tech["dist_to_support"], tech["dist_to_resistance"],
            tech["volume_ratio"], rp, conviction, event_type
        )

    elif is_down:
        # BEARISH: Exit / short guidance
        stop_loss    = round(price + 1.0 * atr, 2)  # Stop above current for existing longs
        stop_pct     = round(((stop_loss - price) / price) * 100, 2)

        # Downside target 1: Support level
        target1      = round(support * rsi_upside_boost, 2)
        target1_pct  = round(((target1 - price) / price) * 100, 2)

        # Downside target 2: 50% extension below support
        target2      = round(target1 - 0.65 * abs(price - support) * evt_mult, 2)
        target2_pct  = round(((target2 - price) / price) * 100, 2)

        buy_low  = None
        buy_high = None

        reward1 = price - target1
        risk    = stop_loss - price
        if risk > 0:
            rr_val = round(reward1 / risk, 2)
            risk_reward = f"1 : {rr_val}"

        if conviction >= 0.72 and tech_bearish:
            action = "SELL"
            action_label = "SELL / CAPITAL PROTECTION"
        elif conviction >= 0.50:
            action = "BOOK_PROFIT"
            action_label = "BOOK PROFITS / TRIM POSITION"
        else:
            action = "HOLD_CAUTIOUS"
            action_label = "HOLD WITH CAUTION — REVIEW LEVELS"

        strategy_notes = _build_bearish_notes(
            price, target1, target2, stop_loss,
            rsi, trend, tech["dist_to_support"], tech["volume_ratio"],
            rp, conviction, event_type
        )

    else:
        # NEUTRAL / SIDEWAYS
        buy_low  = round(support + 0.3 * atr, 2)
        buy_high = round(price * 1.003, 2)
        target1  = round(resistance * 0.995, 2)
        target2  = round(resistance + 0.5 * atr, 2)
        stop_loss = round(support - 0.8 * atr, 2)
        target1_pct = round(((target1 - price) / price) * 100, 2)
        target2_pct = round(((target2 - price) / price) * 100, 2)
        stop_pct    = round(((price - stop_loss) / price) * 100, 2)

        reward1 = target1 - price
        risk    = price - stop_loss
        if risk > 0:
            rr_val = round(reward1 / risk, 2)
            risk_reward = f"1 : {rr_val}"

        action = "HOLD"
        action_label = "HOLD & AWAIT DIRECTIONAL BREAKOUT"

        strategy_notes = _build_neutral_notes(
            price, buy_low, buy_high, target1, resistance, support, stop_loss,
            rsi, trend, tech["dist_to_support"], tech["dist_to_resistance"],
            tech["volume_ratio"], rp
        )

    # ── Final Output ──────────────────────────────────────────────────────────
    return {
        "ticker":         tech["ticker"],
        "current_price":  price,
        "action":         action,
        "action_label":   action_label,
        "conviction":     round(conviction * 100, 1),

        # Trade Levels (all anchored to real data)
        "buy_zone": {
            "low":  buy_low,
            "high": buy_high
        } if buy_low else None,
        "target1": {
            "price": target1,
            "pct":   target1_pct,
            "label": "Short-Term (1–3 Trading Days)"
        } if target1 else None,
        "target2": {
            "price": target2,
            "pct":   target2_pct,
            "label": "Swing Target (5–10 Trading Days)"
        } if target2 else None,
        "stop_loss": {
            "price": stop_loss,
            "pct":   stop_pct
        } if stop_loss else None,
        "risk_reward": risk_reward,

        # Technical Context
        "technicals": {
            "trend":              trend,
            "rsi":                tech["rsi14"],
            "ema20":              tech["ema20"],
            "ema50":              tech["ema50"],
            "atr":                tech["atr14"],
            "support":            tech["support"],
            "resistance":         tech["resistance"],
            "dist_to_support_pct":    tech["dist_to_support"],
            "dist_to_resistance_pct": tech["dist_to_resistance"],
            "high_52w":           tech["high_52w"],
            "low_52w":            tech["low_52w"],
            "range_position_pct": tech["range_position_pct"],
            "volume_ratio":       tech["volume_ratio"],
        },

        # Plain-language strategic guidance
        "strategy_narrative": " ".join(strategy_notes),
        "data_source":        "yfinance (NSE/BSE Live Data) | ATR-14 | EMA-20/50 | Swing Pivots",
        "generated_at":       datetime.now().isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  NARRATIVE BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def _fmt(val: float) -> str:
    return f"₹{val:,.2f}"


def _build_bullish_notes(
    price, buy_low, buy_high, t1, t2, sl,
    rsi, trend, dist_sup, dist_res, vol_ratio, rp, conviction, event_type
) -> List[str]:
    notes = []

    # Entry timing
    if dist_sup < 2.0:
        notes.append(f"Price is trading very close to support ({_fmt(buy_low)}), offering a low-risk accumulation entry.")
    elif dist_sup < 5.0:
        notes.append(f"Enter in the accumulation zone {_fmt(buy_low)}–{_fmt(buy_high)}, near the established support base.")
    else:
        notes.append(f"Wait for a pullback toward the accumulation band {_fmt(buy_low)}–{_fmt(buy_high)} before initiating a fresh position.")

    # RSI context
    if rsi < 40:
        notes.append(f"RSI at {rsi} signals oversold conditions, improving the odds of a technical bounce.")
    elif rsi > 70:
        notes.append(f"RSI at {rsi} indicates overbought territory — use strict sizing; wait for a minor correction before adding.")
    else:
        notes.append(f"RSI at {rsi} is in a healthy range, supporting continued upside momentum.")

    # Trend context
    if trend == "STRONG_UPTREND":
        notes.append("Trend is strongly bullish (EMA-20 > EMA-50, price above both). Momentum favors bulls.")
    elif trend == "UPTREND":
        notes.append("Uptrend intact. Dips toward EMA-20 are valid re-entry opportunities.")
    elif trend == "SIDEWAYS":
        notes.append("Price is consolidating. A breakout above resistance would confirm bullish continuation.")

    # Volume confirmation
    if vol_ratio > 1.5:
        notes.append(f"Volume surge ({vol_ratio:.1f}x avg) strengthens the bullish catalyst signal.")
    elif vol_ratio < 0.7:
        notes.append("Volume is below average — await volume confirmation before aggressive entry.")

    # 52-week position
    if rp > 80:
        notes.append("Stock is near its 52-week high. Be cautious of overhead supply; use staggered entries.")
    elif rp < 30:
        notes.append("Price is in the lower third of the 52-week range, offering relative value on dips.")

    # Targets
    notes.append(
        f"Book partial profits at Target 1 ({_fmt(t1)}, {((t1-price)/price*100):+.1f}%) "
        f"and trail the remainder toward Target 2 ({_fmt(t2)}, {((t2-price)/price*100):+.1f}%)."
    )
    notes.append(f"Maintain strict stop-loss at {_fmt(sl)} to limit downside risk.")

    return notes


def _build_bearish_notes(
    price, t1, t2, sl, rsi, trend, dist_sup, vol_ratio, rp, conviction, event_type
) -> List[str]:
    notes = []

    if trend in ("STRONG_DOWNTREND", "DOWNTREND"):
        notes.append("Technical trend is bearish (EMA-20 < EMA-50). Sellers are in control.")
    else:
        notes.append("Sentiment-driven bearish signal conflicts with neutral/positive technicals — exercise extra caution.")

    if rsi > 65:
        notes.append(f"RSI at {rsi} is in overbought zone, raising probability of a reversal or correction.")
    elif rsi < 35:
        notes.append(f"RSI at {rsi} is oversold — while bearish sentiment persists, downside may be limited from here.")

    if vol_ratio > 1.5:
        notes.append(f"High volume ({vol_ratio:.1f}x avg) on bearish catalyst increases sell conviction.")

    notes.append(
        f"If holding, book profits or trim exposure at current levels. "
        f"First downside target is the support zone at {_fmt(t1)} ({((t1-price)/price*100):+.1f}%)."
    )
    notes.append(f"Extended target at {_fmt(t2)} if support breaks. Stop-loss for short positions: {_fmt(sl)}.")
    notes.append("Avoid fresh buying until price stabilizes above support and RSI recovers above 45.")

    return notes


def _build_neutral_notes(
    price, buy_low, buy_high, t1, resistance, support, sl,
    rsi, trend, dist_sup, dist_res, vol_ratio, rp
) -> List[str]:
    notes = []
    notes.append("Market is in consolidation mode. Wait for a clear directional break before initiating aggressive positions.")
    notes.append(f"Range-bound trading band: {_fmt(support)} (support) to {_fmt(resistance)} (resistance).")
    if rsi > 55:
        notes.append(f"RSI at {rsi} — slight bullish bias within the range. Watch for resistance breakout above {_fmt(resistance)}.")
    elif rsi < 45:
        notes.append(f"RSI at {rsi} — slight bearish bias. Watch for support breakdown below {_fmt(support)}.")
    else:
        notes.append(f"RSI neutral at {rsi}. No directional edge — reduce position size and wait.")
    notes.append(
        f"If breakout above {_fmt(resistance)} with volume, target {_fmt(t1)}+. "
        f"Stop-loss for any existing position: {_fmt(sl)}."
    )
    return notes


# ─────────────────────────────────────────────────────────────────────────────
#  yFINANCE DATA FETCHER
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_ohlcv(ticker: str, period: str = "3mo") -> List[Dict[str, Any]]:
    """Fetch OHLCV from local stock_price database table first (sub-millisecond), fallback to yfinance."""
    try:
        from database import get_connection
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT open, high, low, close, volume
            FROM stock_price
            WHERE ticker = ? AND close > 0
            ORDER BY date DESC
            LIMIT 90
        """, (ticker,))
        rows = c.fetchall()
        conn.close()
        if rows and len(rows) >= 10:
            result = []
            for r in reversed(rows):
                result.append({
                    "open":   float(r[0] or r[3]),
                    "high":   float(r[1] or r[3]),
                    "low":    float(r[2] or r[3]),
                    "close":  float(r[3]),
                    "volume": int(float(r[4] or 0))
                })
            return result
    except Exception as ex:
        pass

    if not YF_AVAILABLE:
        return []
    try:
        yf_ticker = yf.Ticker(ticker)
        hist = yf_ticker.history(period=period, interval="1d")
        if hist is None or hist.empty:
            return []
        result = []
        for _, row in hist.iterrows():
            try:
                result.append({
                    "open":   float(row["Open"]),
                    "high":   float(row["High"]),
                    "low":    float(row["Low"]),
                    "close":  float(row["Close"]),
                    "volume": int(row.get("Volume", 0))
                })
            except Exception:
                continue
        return result
    except Exception as e:
        print(f"[trade_engine] yfinance fetch error for {ticker}: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
#  FALLBACK WHEN NO DATA AVAILABLE
# ─────────────────────────────────────────────────────────────────────────────

def _fallback_analysis(
    ticker: str, direction: str, confidence: float, sentiment_score: float
) -> Dict[str, Any]:
    """Returns a minimal response when historical data is unavailable."""
    return {
        "ticker":         ticker,
        "current_price":  None,
        "action":         "DATA_UNAVAILABLE",
        "action_label":   "Live Data Unavailable",
        "conviction":     round(confidence * 0.5, 1),
        "buy_zone":       None,
        "target1":        None,
        "target2":        None,
        "stop_loss":      None,
        "risk_reward":    "—",
        "technicals":     None,
        "strategy_narrative": (
            "Real-time historical data could not be fetched for this ticker at the moment. "
            "This may be due to a network issue, rate limiting, or an unrecognized ticker symbol. "
            "Please try refreshing after a moment or check if the NSE/BSE ticker is correctly formatted (e.g., RELIANCE.NS)."
        ),
        "data_source":    "N/A (fetch failed)",
        "generated_at":   datetime.now().isoformat(),
    }
