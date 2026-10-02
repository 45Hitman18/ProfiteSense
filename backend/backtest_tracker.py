"""
backtest_tracker.py — Real Backtesting Engine for Market News AI
================================================================
Computes genuine directional accuracy by:
1. Looking up actual post-news stock returns from the stored stock_price table
2. Comparing NLP-predicted direction (UP/DOWN/NEUTRAL) vs actual price movement
3. Breaking down by horizon (1d, 3d, 5d), impact level, and sector

NO FABRICATED NUMBERS. If stock data is unavailable, "INSUFFICIENT DATA" is shown.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from collections import defaultdict

from database import get_connection

logger = logging.getLogger("backtest_tracker")


def _get_future_return(ticker: str, pub_date: str, n_days: int, conn) -> Optional[float]:
    """
    Look up actual stock return n trading days after pub_date.
    Returns return% or None if data unavailable.
    """
    try:
        entries = conn.execute(
            "SELECT date, close FROM stock_price WHERE ticker=? ORDER BY date ASC",
            (ticker,)
        ).fetchall()
        if not entries:
            return None

        prices = [(r["date"], float(r["close"])) for r in entries if r["close"]]

        # Start price: first trading day on or after pub_date
        start_entries = [(d, p) for d, p in prices if d >= pub_date]
        if not start_entries:
            return None
        start_date, start_price = start_entries[0]
        if start_price <= 0:
            return None

        # Target date: n calendar days after pub_date (with ±4 trading day buffer)
        ref_dt = datetime.strptime(pub_date[:10], "%Y-%m-%d")
        min_target = (ref_dt + timedelta(days=n_days)).strftime("%Y-%m-%d")
        max_target = (ref_dt + timedelta(days=n_days + 6)).strftime("%Y-%m-%d")

        end_entries = [(d, p) for d, p in prices if min_target <= d <= max_target]
        if not end_entries:
            return None
        _, end_price = end_entries[0]
        if end_price <= 0:
            return None

        return ((end_price - start_price) / start_price) * 100
    except Exception as e:
        logger.debug("Return lookup failed for %s at %s: %s", ticker, pub_date, e)
        return None


def _direction_correct(predicted: str, actual_return_pct: float, threshold: float = 0.5) -> Optional[bool]:
    """
    Check if predicted direction agrees with actual stock movement.
    - UP predicted → actual > +threshold%: correct
    - DOWN predicted → actual < -threshold%: correct
    - NEUTRAL predicted → -threshold <= actual <= +threshold: correct
    Returns None if actual_return is None (uninferrable).
    """
    if predicted == "UP":
        return actual_return_pct > threshold
    elif predicted == "DOWN":
        return actual_return_pct < -threshold
    elif predicted == "NEUTRAL":
        return -threshold <= actual_return_pct <= threshold
    return None


def compute_real_backtest() -> Dict[str, Any]:
    """
    Core backtesting function. Loads all predictions from analysis table,
    looks up actual returns from stock_price, and computes real accuracy metrics.
    """
    conn = get_connection()

    # Fetch all predictions where we have ticker + published date
    rows = conn.execute("""
        SELECT
            an.article_id,
            an.ticker,
            an.direction,
            an.impact_level,
            an.confidence,
            an.sector,
            an.event_type,
            an.sentiment_score,
            a.published_at
        FROM analysis an
        JOIN articles a ON an.article_id = a.id
        WHERE an.ticker IS NOT NULL
          AND an.direction IN ('UP', 'DOWN', 'NEUTRAL')
          AND a.published_at IS NOT NULL
        ORDER BY a.published_at DESC
        LIMIT 500
    """).fetchall()

    if not rows:
        conn.close()
        return {
            "status": "INSUFFICIENT_DATA",
            "message": "No predictions with ticker data found. Sync news and collect prices first.",
            "total_evaluated": 0,
            "has_real_data": False,
            "compliance_disclaimer": "AI/model estimate — not investment advice."
        }

    # Quick diagnostic: check date alignment between articles and price data
    try:
        price_min = conn.execute("SELECT MIN(date) FROM stock_price").fetchone()[0]
        price_max = conn.execute("SELECT MAX(date) FROM stock_price").fetchone()[0]
    except Exception:
        price_min, price_max = None, None

    # Evaluate each prediction across 3 horizons
    horizon_configs = [("1d", 1), ("3d", 3), ("5d", 5)]

    horizon_stats = {}
    for h_label, n_days in horizon_configs:
        correct = 0
        total = 0
        returns_by_impact = defaultdict(list)
        returns_by_sector = defaultdict(list)
        direction_counts = defaultdict(int)

        for r in rows:
            ticker = r["ticker"]
            pub_date = str(r["published_at"])[:10]
            direction = r["direction"]
            impact = r["impact_level"] or "MEDIUM"
            sector = r["sector"] or "Broad Market"

            actual_ret = _get_future_return(ticker, pub_date, n_days, conn)
            if actual_ret is None:
                continue  # Skip: no price data for this ticker/date

            is_correct = _direction_correct(direction, actual_ret)
            if is_correct is None:
                continue

            total += 1
            if is_correct:
                correct += 1
            direction_counts[direction] += 1
            returns_by_impact[impact].append((is_correct, actual_ret))
            returns_by_sector[sector].append((is_correct, actual_ret))

        accuracy = round((correct / total) * 100, 1) if total > 0 else None

        impact_accuracy = {}
        for impact_key, pairs in returns_by_impact.items():
            n = len(pairs)
            c = sum(1 for ok, _ in pairs if ok)
            impact_accuracy[impact_key] = {
                "accuracy_pct": round((c / n) * 100, 1) if n > 0 else None,
                "n": n
            }

        sector_accuracy = {}
        for sec_key, pairs in returns_by_sector.items():
            n = len(pairs)
            c = sum(1 for ok, _ in pairs if ok)
            sector_accuracy[sec_key] = {
                "accuracy_pct": round((c / n) * 100, 1) if n > 0 else None,
                "n": n
            }

        horizon_stats[h_label] = {
            "accuracy_pct": accuracy,
            "correct": correct,
            "total_evaluated": total,
            "direction_distribution": dict(direction_counts),
            "impact_accuracy": impact_accuracy,
            "sector_accuracy": sector_accuracy,
        }

    conn.close()

    # Overall stats
    all_totals = [v["total_evaluated"] for v in horizon_stats.values()]
    all_correct = [v["correct"] for v in horizon_stats.values()]

    grand_total = sum(all_totals)
    grand_correct = sum(all_correct)
    overall_accuracy = round((grand_correct / grand_total) * 100, 1) if grand_total > 0 else None

    # Gather HIGH impact accuracy from 3d horizon as headline metric
    h3 = horizon_stats.get("3d", {})
    high_acc = h3.get("impact_accuracy", {}).get("HIGH", {}).get("accuracy_pct")
    med_acc  = h3.get("impact_accuracy", {}).get("MEDIUM", {}).get("accuracy_pct")
    low_acc  = h3.get("impact_accuracy", {}).get("LOW", {}).get("accuracy_pct")

    # Add price range diagnostic for UI messaging
    price_range_info = None
    if price_min and price_max:
        price_range_info = "{} to {}".format(price_min, price_max)

    insufficient_msg = (
        f"Articles and stock price data don't overlap for backtesting yet. "
        f"Price data available: {price_range_info or 'none'}. "
        "As new news is synced over the coming days, backtest will automatically compute."
    ) if grand_total == 0 else None

    return {
        "status": "computed" if grand_total > 0 else "INSUFFICIENT_DATA",
        "has_real_data": grand_total > 0,
        "overall_accuracy_pct": overall_accuracy,
        "total_evaluated": grand_total,
        "horizon_1d_accuracy": horizon_stats.get("1d", {}).get("accuracy_pct"),
        "horizon_3d_accuracy": horizon_stats.get("3d", {}).get("accuracy_pct"),
        "horizon_5d_accuracy": horizon_stats.get("5d", {}).get("accuracy_pct"),
        "high_impact_accuracy": high_acc,
        "medium_impact_accuracy": med_acc,
        "low_impact_accuracy": low_acc,
        "horizons": horizon_stats,
        "price_data_range": price_range_info,
        "message": insufficient_msg,
        "note": (
            "All accuracy values computed from actual post-news stock returns stored in the database."
            if grand_total > 0
            else insufficient_msg or "Insufficient data for backtesting."
        ),
        "methodology": (
            "Directional accuracy: UP prediction = correct if stock closed >+0.5% within horizon. "
            "DOWN prediction = correct if stock closed <-0.5% within horizon. "
            "NEUTRAL = correct if -0.5% ≤ actual return ≤ +0.5%."
        ),
        "compliance_disclaimer": "AI/model estimate — not investment advice. Past accuracy does not guarantee future returns.",
        "computed_at": datetime.now().isoformat(),
    }


def get_accuracy_metrics() -> dict:
    """
    Public API wrapper. Returns real backtested accuracy or INSUFFICIENT_DATA if
    stock price data is unavailable. Never fabricates numbers.
    """
    try:
        return compute_real_backtest()
    except Exception as e:
        logger.error("Backtest computation failed: %s", e)
        return {
            "status": "error",
            "message": f"Backtest computation error: {str(e)}",
            "has_real_data": False,
            "compliance_disclaimer": "AI/model estimate — not investment advice."
        }
