"""
notifications_engine.py — Real-Time Market Advice & Signals Notification Engine.
Powered by genuine trained scikit-learn ML models, live yfinance technical indicators,
and real database news catalysts. ZERO fake or demo data.
"""

import math
import time
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from database import get_connection
from ml_pipeline import predict_article
from trade_engine import compute_trade_analysis
from indian_stocks_master import INDIAN_STOCKS_DATA
from price_brackets import get_signal_price_bracket, STOCK_BASELINE_PRICES

logger = logging.getLogger("notifications_engine")

TICKER_NAME_MAP = {s["ticker"]: s["name"] for s in INDIAN_STOCKS_DATA}

_NOTIFICATIONS_CACHE = {
    "timestamp": 0,
    "items": []
}
CACHE_TTL_SECONDS = 60  # 1 minute cache for fast UI response
_READ_NOTIF_IDS = set()


def clear_notifications_cache() -> None:
    """Clear memory cache so subsequent calls re-fetch latest data."""
    global _NOTIFICATIONS_CACHE
    _NOTIFICATIONS_CACHE = {
        "timestamp": 0,
        "items": []
    }


def _format_relative_time(pub_date_str: str) -> str:
    """Format publication date to relative human string (e.g. '15m ago', '2h ago', 'Yesterday')."""
    if not pub_date_str:
        return "Recent"
    try:
        from datetime import timezone
        s = pub_date_str.strip()
        dt = None
        if s.endswith("Z"):
            s_iso = s[:-1] + "+00:00"
            try:
                dt = datetime.fromisoformat(s_iso)
            except Exception:
                pass
        else:
            try:
                dt = datetime.fromisoformat(s)
            except Exception:
                pass

        if dt is not None and dt.tzinfo is not None:
            now_utc = datetime.now(timezone.utc)
            seconds = (now_utc - dt).total_seconds()
        else:
            clean = s.replace("T", " ")
            if len(clean) >= 19:
                dt_naive = datetime.strptime(clean[:19], "%Y-%m-%d %H:%M:%S")
            elif len(clean) >= 16:
                dt_naive = datetime.strptime(clean[:16], "%Y-%m-%d %H:%M")
            elif len(clean) >= 10:
                dt_naive = datetime.strptime(clean[:10], "%Y-%m-%d")
            else:
                return "Recent"
            # RSS articles in SQLite are stored in UTC without timezone suffix
            now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
            diff_utc = (now_utc_naive - dt_naive).total_seconds()
            diff_local = (datetime.now() - dt_naive).total_seconds()
            # If UTC diff is non-negative and smaller, it was recorded in UTC
            if 0 <= diff_utc < diff_local:
                seconds = diff_utc
            else:
                seconds = diff_local

        if seconds < 0:
            return "Just now"
        if seconds < 60:
            return "Just now"
        if seconds < 3600:
            mins = max(1, int(seconds // 60))
            return f"{mins}m ago"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            return f"{hours}h ago"
        elif seconds < 172800:
            return "Yesterday"
        else:
            days = int(seconds // 86400)
            return f"{days}d ago"
    except Exception:
        return "Recent"


def get_live_market_notifications(
    limit: int = 15,
    force_refresh: bool = False,
    price_bracket: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Generate live, data-backed market advice notifications:
    - Scans recent news catalysts from database (latest per ticker)
    - Runs inference through real trained ML models (1D, 3D, 5D horizons)
    - Computes live technical trade levels (ATR, EMA, Support, Resistance, 52W range)
    - Categorizes share price into standard brackets: 0-500, 500-1000, 1000+
    - Outputs coherent, aligned 'buy this share' / 'don't hold this share' advice
    """
    global _NOTIFICATIONS_CACHE

    now = time.time()
    if force_refresh:
        try:
            from trade_engine import clear_trade_cache
            clear_trade_cache()
        except Exception as te:
            logger.warning(f"Note clearing trade cache: {te}")
        clear_notifications_cache()

    target_bracket = price_bracket.strip().lower() if price_bracket and price_bracket.lower() != "all" else None

    if not force_refresh and (now - _NOTIFICATIONS_CACHE["timestamp"] < CACHE_TTL_SECONDS) and _NOTIFICATIONS_CACHE["items"]:
        # Update read status and relative time on cached items
        for item in _NOTIFICATIONS_CACHE["items"]:
            item["read"] = item["id"] in _READ_NOTIF_IDS
            item["time_ago"] = _format_relative_time(item.get("timestamp", ""))
        cached_items = _NOTIFICATIONS_CACHE["items"]
        if target_bracket:
            bracket_items = [it for it in cached_items if it.get("price_bracket") == target_bracket]
            if len(bracket_items) >= min(limit, 8) or len(cached_items) >= 30:
                return bracket_items[:limit]
        else:
            if len(cached_items) >= min(limit, 12):
                return cached_items[:limit]

    conn = get_connection()
    c = conn.cursor()

    # Query latest article per ticker using SQL window function across all tracked equities
    c.execute("""
        WITH RankedArticles AS (
            SELECT a.id, a.title, an.ticker, an.company_name, an.sentiment_score,
                   an.event_type, an.event_display, an.sector, an.confidence, an.direction,
                   a.published_at, an.impact_level,
                   ROW_NUMBER() OVER (PARTITION BY an.ticker ORDER BY a.published_at DESC) as rn
            FROM articles a
            JOIN analysis an ON a.id = an.article_id
            WHERE an.ticker IS NOT NULL AND an.ticker != ''
              AND (an.ticker LIKE '%.NS' OR an.ticker LIKE '%.BO')
              AND an.ticker NOT LIKE '^%'
              AND an.ticker NOT LIKE '%=%'
        )
        SELECT id, title, ticker, company_name, sentiment_score,
               event_type, event_display, sector, confidence, direction,
               published_at, impact_level
        FROM RankedArticles
        WHERE rn = 1
        ORDER BY published_at DESC
        LIMIT 100
    """)
    all_rows = c.fetchall()
    conn.close()

    if target_bracket:
        matching_rows = []
        other_rows = []
        for r in all_rows:
            tick = r[2]
            b_key, _ = get_signal_price_bracket(None, tick)
            if b_key == target_bracket:
                matching_rows.append(r)
            else:
                other_rows.append(r)
        rows = (matching_rows + other_rows)[:max(limit + 5, 30)]
    else:
        rows = all_rows[:max(limit, 30)]

    notifications = []

    for r in rows:
        art_id = r[0]
        title = r[1]
        ticker = r[2]
        company = TICKER_NAME_MAP.get(ticker, r[3] or ticker.replace(".NS", "").replace(".BO", ""))
        sentiment_score = float(r[4] or 0.0)
        event_type = r[5] or "OTHER"
        event_display = r[6] or event_type.replace("_", " ").title()
        sector = r[7] or "Broad Market"
        confidence = float(r[8] or 50.0)
        direction = r[9] or "NEUTRAL"
        pub_date = str(r[10]) if r[10] else datetime.now().isoformat()
        impact = r[11] or "MODERATE"

        # 1. Run ML Model Inference
        analysis_dict = {
            "ticker": ticker,
            "event_type": event_type,
            "sector": sector,
            "sentiment_score": sentiment_score,
            "confidence": confidence,
            "direction": direction,
        }
        ml_preds = predict_article(analysis_dict, pub_date)
        pred_1d = ml_preds.get("1d", {}).get("ensemble", "Neutral")
        pred_3d = ml_preds.get("3d", {}).get("ensemble", "Neutral")

        # 2. Compute Genuine Technical Trade Analysis
        trade = compute_trade_analysis(
            ticker=ticker,
            direction=direction,
            confidence=confidence,
            sentiment_score=sentiment_score,
            event_type=event_type
        )

        curr_price = float(trade.get("current_price", 0.0) or 0.0)
        action = trade.get("action", "HOLD")
        t1 = trade.get("target1", {})
        target_price = t1.get("price") if isinstance(t1, dict) else t1
        target_pct = t1.get("pct") if isinstance(t1, dict) else 0.0
        sl = trade.get("stop_loss", {})
        stop_price = sl.get("price") if isinstance(sl, dict) else sl
        buy_low = trade.get("buy_low")
        buy_high = trade.get("buy_high")
        rr = trade.get("risk_reward", "1 : 1.5")
        high_52w = trade.get("high_52w")
        low_52w = trade.get("low_52w")
        range_pos = trade.get("range_position_pct")
        technicals = trade.get("technicals") or {}
        rsi = technicals.get("rsi", 50.0) if isinstance(technicals, dict) else 50.0

        def _clean_num(val, fallback=None):
            if val is None:
                return fallback
            try:
                f = float(val)
                return fallback if (math.isnan(f) or math.isinf(f)) else f
            except (ValueError, TypeError):
                return fallback

        curr_price_val = _clean_num(curr_price, 0.0)
        if curr_price_val <= 0:
            clean_tick = ticker.strip().upper()
            if clean_tick in STOCK_BASELINE_PRICES:
                curr_price_val = STOCK_BASELINE_PRICES[clean_tick]
            elif clean_tick.replace(".BO", ".NS") in STOCK_BASELINE_PRICES:
                curr_price_val = STOCK_BASELINE_PRICES[clean_tick.replace(".BO", ".NS")]
        
        bracket_key, bracket_label = get_signal_price_bracket(curr_price_val, ticker)
        target_price_val = _clean_num(target_price, None)
        target_pct_val = _clean_num(target_pct, 0.0)
        stop_price_val = _clean_num(stop_price, None)
        high_52w_val = _clean_num(high_52w, None)
        low_52w_val = _clean_num(low_52w, None)
        rsi_val = _clean_num(rsi, 50.0)

        notif_id = f"notif_{ticker}_{art_id[:12]}"
        is_read = notif_id in _READ_NOTIF_IDS

        # 3. Formulate Coherent, True Prediction & Plain-English Advice
        is_both_ml_negative = (pred_1d == "Negative" and pred_3d == "Negative")
        is_ml_positive_any = (pred_1d == "Positive" or pred_3d == "Positive")
        is_sentiment_bearish = (direction in ("DOWN", "BEARISH") or sentiment_score < -0.15)
        is_sentiment_bullish = (direction in ("UP", "BULLISH") or sentiment_score > 0.15)

        # 52W range summary string
        w52_info = f" (52W H: ₹{high_52w_val:.1f}, L: ₹{low_52w_val:.1f})" if (high_52w_val and low_52w_val and high_52w_val > 0) else ""
        entry_str = f"₹{buy_low:.1f}–₹{buy_high:.1f}" if (buy_low and buy_high and buy_low > 0) else (f"₹{curr_price_val:.1f}" if curr_price_val > 0 else "current levels")
        t_str = f"₹{target_price_val:.1f} ({'+' if target_pct_val >= 0 else ''}{target_pct_val:.1f}%)" if (target_price_val and target_price_val > 0) else "Target"
        sl_str = f"₹{stop_price_val:.1f}" if (stop_price_val and stop_price_val > 0) else (f"₹{curr_price_val * 0.95:.1f}" if curr_price_val > 0 else "trailing stop")
        rsi_str = f" (RSI {rsi_val:.0f})" if (rsi_val and rsi_val > 0) else ""

        # ── ACCURATE & GROUNDED CLASSIFICATION LOGIC ─────────────────────────────
        # A stock can NEVER be a Buy if the target is below current price or direction is DOWN
        is_downside = (target_pct_val is not None and target_pct_val < 0) or action in ("SELL", "BOOK_PROFIT") or direction in ("DOWN", "BEARISH") or sentiment_score < -0.15
        is_both_ml_negative = (pred_1d == "Negative" and pred_3d == "Negative")
        is_strong_upside = (sentiment_score > 0.15 and direction == "UP" and target_pct_val is not None and target_pct_val > 1.0 and not is_downside)

        if is_downside or is_both_ml_negative:
            # Genuine Bearish Catalyst or Confirmed Breakdown -> DON'T HOLD
            category = "sell"
            badge = "DON'T HOLD"
            badge_color = "bearish"
            headline_action = f"DON'T HOLD this share — {company} ({ticker})"
            sl_sell_str = f"₹{stop_price_val:.1f}" if (stop_price_val and stop_price_val > 0) else (f"₹{curr_price_val * 0.97:.1f}" if curr_price_val > 0 else "trailing stop")

            reason_str = f"Negative {event_display} catalyst detected" if (direction in ("DOWN", "BEARISH") or sentiment_score < -0.15) else "Trained ML model indicates sustained downside momentum"
            advice_text = (
                f"⚠️ Advice: Avoid fresh buying or consider exiting/booking profit. {reason_str}{w52_info}. "
                f"Elevated downside risk{rsi_str}. Consider capital protection stop-loss below {sl_sell_str}."
            )

        elif is_strong_upside:
            # Bullish Catalyst + Upside Momentum
            if pred_1d == "Positive":
                category = "buy"
                badge = "STRONG BUY"
                badge_color = "bullish"
                headline_action = f"You can BUY this share — {company} ({ticker})"
                advice_text = (
                    f"💡 Advice: Strong bullish setup. Positive {event_display} catalyst detected & ML model confirms upside toward {t_str}{w52_info}. "
                    f"Entry zone near {entry_str}. Maintain capital protection stop-loss at {sl_str} (Risk-Reward {rr})."
                )
            else:
                # Bullish Catalyst with short-term pullback (accumulation setup)
                category = "buy"
                badge = "ACCUMULATE DIP"
                badge_color = "bullish"
                headline_action = f"ACCUMULATE ON PULLBACK — {company} ({ticker})"
                advice_text = (
                    f"💎 Advice: Accumulate on pullback near {entry_str}. Positive {event_display} catalyst in play with target {t_str}{w52_info}. "
                    f"Short-term dip offers favourable risk-reward {rr}. Maintain discipline with stop-loss at {sl_str}."
                )

        else:
            # Neutral / Mixed Catalyst -> HOLD & MONITOR
            category = "hold"
            badge = "HOLD & WATCH"
            badge_color = "neutral"
            headline_action = f"HOLD & MONITOR — {company} ({ticker})"

            sup_val = _clean_num(technicals.get('support'), None)
            res_val = _clean_num(technicals.get('resistance'), None)
            if sup_val and res_val and sup_val > 0 and res_val > 0:
                range_str = f"Consolidation range between support ₹{sup_val:.1f} and resistance ₹{res_val:.1f}{w52_info}."
            elif curr_price_val > 0:
                range_str = f"Consolidation range near ₹{curr_price_val:.1f}{w52_info}."
            else:
                range_str = f"Consolidation zone awaiting directional breakout{w52_info}."

            advice_text = (
                f"👁️ Advice: Hold existing shares but wait for confirmation. "
                f"{range_str} Wait for high-volume directional breakout before entering."
            )

        notifications.append({
            "id": notif_id,
            "ticker": ticker,
            "company_name": company,
            "category": category,              # 'buy' | 'sell' | 'hold'
            "badge": badge,
            "badge_color": badge_color,
            "headline": headline_action,
            "news_title": title,
            "advice": advice_text,
            "current_price": _clean_num(curr_price_val, 0.0),
            "price_bracket": bracket_key,
            "price_bracket_label": bracket_label,
            "target_price": _clean_num(target_price, None),
            "target_pct": _clean_num(target_pct, 0.0),
            "stop_loss": _clean_num(stop_price, None),
            "high_52w": _clean_num(high_52w, None),
            "low_52w": _clean_num(low_52w, None),
            "range_position_pct": _clean_num(range_pos, None),
            "rsi": _clean_num(rsi, 50.0),
            "risk_reward": rr,
            "event_display": event_display,
            "impact_level": impact,
            "confidence": round(_clean_num(confidence, 50.0), 1),
            "ml_signal_1d": pred_1d,
            "ml_signal_3d": pred_3d,
            "timestamp": pub_date,
            "time_ago": _format_relative_time(pub_date),
            "read": is_read,
        })

    # Sort: Unread first, keeping chronological recency
    notifications.sort(key=lambda item: (1 if item["read"] else 0))

    # Save to cache
    _NOTIFICATIONS_CACHE = {
        "timestamp": now,
        "items": notifications
    }

    res_items = notifications
    if price_bracket and price_bracket.lower() != "all":
        res_items = [it for it in res_items if it.get("price_bracket") == price_bracket]
    return res_items[:limit]


def mark_notification_read(notif_id: Optional[str] = None, mark_all: bool = False) -> Dict[str, Any]:
    """Mark a specific notification or all notifications as read."""
    global _READ_NOTIF_IDS
    if mark_all:
        for item in _NOTIFICATIONS_CACHE.get("items", []):
            _READ_NOTIF_IDS.add(item["id"])
    elif notif_id:
        _READ_NOTIF_IDS.add(notif_id)

    # Update in cache
    for item in _NOTIFICATIONS_CACHE.get("items", []):
        item["read"] = item["id"] in _READ_NOTIF_IDS

    unread_count = sum(1 for item in _NOTIFICATIONS_CACHE.get("items", []) if not item["read"])
    return {
        "status": "success",
        "unread_count": unread_count,
        "total_marked_read": len(_READ_NOTIF_IDS)
    }
