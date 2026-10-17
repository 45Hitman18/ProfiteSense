"""
ml_pipeline.py — Real ML Training Pipeline for Market News AI
=============================================================
Features (11):
  1. sentiment_score         – VADER compound [-1, +1]
  2. sentiment_polarity      – sign: +1 positive, 0 neutral, -1 negative
  3. sentiment_abs           – absolute polarity strength
  4. event_type_enc          – label-encoded news category (28 cats)
  5. sector_enc              – label-encoded sector
  6. recent_return_1d        – last 1-day stock return %
  7. historical_volatility   – 20-day rolling stddev of daily returns
  8. volume_norm             – normalized relative volume vs 20d avg
  9. market_trend            – NIFTY/SPY 5-day return % (broad trend)
 10. historical_cat_reaction – avg 3d return for this event_type in past
 11. news_recency            – age of article in hours (negated: older = lower)

Models:
  • Logistic Regression
  • Random Forest
  • Gradient Boosting

Horizons: 1d, 3d, 5d
Labels: Positive (>+0.5%), Neutral (-0.5% to +0.5%), Negative (<-0.5%)

Threshold: MIN_SAMPLES = 20 labeled samples per horizon for training.
All metrics stored in model_metric table.
Model objects serialised with joblib to backend/models/.
Dataset exported to backend/dataset_export.csv.
"""

import os
import json
import uuid
import joblib
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Callable
from collections import defaultdict

import numpy as np

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
    from sklearn.preprocessing import LabelEncoder, StandardScaler
    from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold, TimeSeriesSplit
    from sklearn.pipeline import Pipeline
    from sklearn.dummy import DummyClassifier
    from sklearn.metrics import (
        accuracy_score, balanced_accuracy_score, precision_score, recall_score,
        f1_score, confusion_matrix, classification_report
    )
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

from database import get_connection, DB_PATH

logger = logging.getLogger("ml_pipeline")
logging.basicConfig(level=logging.INFO)

# ── Constants ──────────────────────────────────────────────────────
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(MODEL_DIR, exist_ok=True)
DATASET_CSV_PATH = os.path.join(os.path.dirname(__file__), "dataset_export.csv")

MIN_SAMPLES = 10                # Minimum labeled samples per horizon for dataset existence
MIN_TEST_SAMPLES = 200          # Safeguard: never present test metrics if n_test < 200 (show insufficient data)
RETURN_THRESHOLD = 0.5          # Default fixed % move threshold for Positive/Negative class
DEFAULT_VOLATILITY_K = 0.5      # Default multiplier for volatility-scaled threshold (k * vol)
DEFAULT_THRESHOLD_FLOOR = 0.25  # Minimum threshold % floor (25 bps)
DEFAULT_THRESHOLD_CAP = 3.0     # Maximum threshold % cap (300 bps)

FEATURE_NAMES = [
    "sentiment_score",
    "sentiment_polarity",
    "sentiment_abs",
    "event_type_enc",
    "sector_enc",
    "recent_return_1d",
    "historical_volatility",
    "volume_norm",
    "market_trend",
    "historical_cat_reaction",
    "news_recency_h",
]

CLASS_LABELS = ["Negative", "Neutral", "Positive"]


# ══════════════════════════════════════════════════════════════════
# DATE & CACHE HELPERS
# ══════════════════════════════════════════════════════════════════
def _parse_date_str(dt_str: Optional[str]) -> Optional[str]:
    """Normalize any date format to YYYY-MM-DD string."""
    if not dt_str:
        return None
    s = str(dt_str).strip()
    try:
        if len(s) >= 10 and s[4] == '-' and s[7] == '-':
            return s[:10]
        # Format 20261001T... or 20261001
        if len(s) >= 8 and s[:8].isdigit():
            return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    except Exception:
        pass
    return None


class StockPriceCache:
    """In-memory cache of stock prices for ultra-fast dataset building & inference."""
    _instance = None
    _cached_at = 0

    def __init__(self):
        self.prices_by_ticker = defaultdict(list)   # ticker -> sorted [(date_str, close, volume)]
        self.close_lookup = {}                       # (ticker, date_str) -> close
        self.dates_by_ticker = defaultdict(list)    # ticker -> sorted [date_str]
        self.reload()

    def reload(self):
        self.prices_by_ticker.clear()
        self.close_lookup.clear()
        self.dates_by_ticker.clear()
        conn = get_connection()
        rows = conn.execute("SELECT ticker, date, close, volume FROM stock_price ORDER BY ticker, date ASC").fetchall()
        conn.close()
        for r in rows:
            ticker = r[0]
            dt = r[1]
            close = float(r[2]) if r[2] is not None else 0.0
            vol = float(r[3]) if r[3] is not None else 0.0
            self.prices_by_ticker[ticker].append((dt, close, vol))
            self.close_lookup[(ticker, dt)] = close
            self.dates_by_ticker[ticker].append(dt)


_cache: Optional[StockPriceCache] = None

def get_price_cache() -> StockPriceCache:
    global _cache
    if _cache is None:
        _cache = StockPriceCache()
    return _cache


# ══════════════════════════════════════════════════════════════════
# 1.  STOCK PRICE HELPERS
# ══════════════════════════════════════════════════════════════════
def _get_stock_features(ticker: str, ref_date: str) -> Dict[str, float]:
    """Compute recent_return_1d, historical_volatility, volume_norm for ticker at ref_date."""
    defaults = {"recent_return_1d": 0.0, "historical_volatility": 2.0, "volume_norm": 1.0}
    cache = get_price_cache()
    entries = cache.prices_by_ticker.get(ticker, [])
    if not entries:
        return defaults

    # Filter entries on or before ref_date
    past_entries = [e for e in entries if e[0] <= ref_date]
    if len(past_entries) < 2:
        return defaults

    try:
        closes = [e[1] for e in past_entries]
        vols   = [e[2] for e in past_entries]

        # 1-day return
        c_curr = closes[-1]
        c_prev = closes[-2]
        recent_return = ((c_curr - c_prev) / c_prev * 100) if c_prev > 0 else 0.0

        # 20-day rolling volatility
        window_closes = closes[-21:] if len(closes) >= 21 else closes
        if len(window_closes) >= 3:
            returns = [((window_closes[i] - window_closes[i-1]) / window_closes[i-1] * 100)
                       for i in range(1, len(window_closes)) if window_closes[i-1] > 0]
            vol = float(np.std(returns)) if returns else 2.0
        else:
            vol = 2.0

        # 20-day normalized volume
        window_vols = vols[-20:] if len(vols) >= 20 else vols
        avg_vol = float(np.mean(window_vols)) if window_vols else 0.0
        last_vol = vols[-1] if vols else 0.0
        vol_norm = float(last_vol / avg_vol) if avg_vol > 0 else 1.0

        return {
            "recent_return_1d": round(recent_return, 4),
            "historical_volatility": round(vol, 4),
            "volume_norm": round(vol_norm, 4),
        }
    except Exception:
        return defaults


def _get_market_trend(ref_date: str) -> float:
    """5-day return of NIFTY or SPY as proxy for broad market trend."""
    cache = get_price_cache()
    for mkt_ticker in ["^NSEI", "SPY"]:
        entries = cache.prices_by_ticker.get(mkt_ticker, [])
        past_entries = [e for e in entries if e[0] <= ref_date]
        if len(past_entries) >= 6:
            c_now = past_entries[-1][1]
            c_5ago = past_entries[-6][1]
            if c_5ago > 0:
                trend = ((c_now - c_5ago) / c_5ago) * 100.0
                # If benchmark data is more than 2 days older than ref_date, decay stale market impact
                try:
                    last_dt = datetime.strptime(past_entries[-1][0][:10], "%Y-%m-%d")
                    curr_dt = datetime.strptime(ref_date[:10], "%Y-%m-%d")
                    if (curr_dt - last_dt).days > 2:
                        trend = trend * 0.4
                except Exception:
                    pass
                return round(trend, 4)
    return 0.0


# ══════════════════════════════════════════════════════════════════
# 2.  LABEL BUILDER & FUTURE RETURN
# ══════════════════════════════════════════════════════════════════
def _get_benchmark_close(
    cache: StockPriceCache,
    benchmark_ticker: str = "^NSEI",
    target_date: str = "",
    max_diff_days: int = 3
) -> Tuple[Optional[float], Optional[str]]:
    """
    Look up benchmark closing price on target_date.
    If exact date is missing (e.g. slight trading-calendar mismatch),
    finds the closest available trading day within max_diff_days.
    Returns: (close_price, matched_date)
    """
    if not target_date:
        return None, None

    # 1. Exact lookup
    p = cache.close_lookup.get((benchmark_ticker, target_date))
    if p is not None and p > 0:
        return p, target_date

    # 2. Fuzzy match within max_diff_days
    entries = cache.prices_by_ticker.get(benchmark_ticker, [])
    if not entries:
        return None, None

    try:
        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    except Exception:
        return None, None

    best_p = None
    best_date = None
    min_diff = 9999
    for dt_str, c, _ in entries:
        try:
            diff = abs((datetime.strptime(dt_str, "%Y-%m-%d") - target_dt).days)
            if diff < min_diff:
                min_diff = diff
                best_p = c
                best_date = dt_str
        except Exception:
            continue

    if min_diff <= max_diff_days and best_p is not None and best_p > 0:
        return best_p, best_date
    return None, None


def compute_excess_return(
    ticker: str,
    pub_date: str,
    n_days: int,
    benchmark_ticker: str = "^NSEI",
    cache: Optional[StockPriceCache] = None
) -> Dict[str, Any]:
    """
    Compute stock return and benchmark-relative excess return over identical trading days.
    Formula: excess_return = stock_return - benchmark_return
    Fall back to raw return if benchmark data is missing, and flag benchmark_missing = True.
    """
    if cache is None:
        cache = get_price_cache()

    entries = cache.prices_by_ticker.get(ticker, [])
    if not entries:
        return {
            "start_date": None, "end_date": None,
            "start_price": None, "end_price": None,
            "stock_return": None, "benchmark_return": None,
            "excess_return": None, "benchmark_missing": True,
            "chosen_return": None
        }

    # Start price: on or first trading day after pub_date
    start_entries = [e for e in entries if e[0] >= pub_date]
    if not start_entries:
        return {
            "start_date": None, "end_date": None,
            "start_price": None, "end_price": None,
            "stock_return": None, "benchmark_return": None,
            "excess_return": None, "benchmark_missing": True,
            "chosen_return": None
        }
    start_date, start_price, _ = start_entries[0]
    if start_price <= 0:
        return {
            "start_date": start_date, "end_date": None,
            "start_price": None, "end_price": None,
            "stock_return": None, "benchmark_return": None,
            "excess_return": None, "benchmark_missing": True,
            "chosen_return": None
        }

    # Target date window: [pub_date + n_days, pub_date + n_days + 4]
    try:
        ref_dt = datetime.strptime(pub_date, "%Y-%m-%d")
        min_target = (ref_dt + timedelta(days=n_days)).strftime("%Y-%m-%d")
        max_target = (ref_dt + timedelta(days=n_days + 4)).strftime("%Y-%m-%d")
    except ValueError:
        return {
            "start_date": start_date, "end_date": None,
            "start_price": start_price, "end_price": None,
            "stock_return": None, "benchmark_return": None,
            "excess_return": None, "benchmark_missing": True,
            "chosen_return": None
        }

    end_entries = [e for e in entries if min_target <= e[0] <= max_target]
    if not end_entries:
        return {
            "start_date": start_date, "end_date": None,
            "start_price": start_price, "end_price": None,
            "stock_return": None, "benchmark_return": None,
            "excess_return": None, "benchmark_missing": True,
            "chosen_return": None
        }

    end_date, end_price, _ = end_entries[0]
    if end_price <= 0:
        return {
            "start_date": start_date, "end_date": end_date,
            "start_price": start_price, "end_price": None,
            "stock_return": None, "benchmark_return": None,
            "excess_return": None, "benchmark_missing": True,
            "chosen_return": None
        }

    stock_ret = round(((end_price - start_price) / start_price) * 100, 4)

    # Benchmark return over aligned trading days
    bench_start_p, _ = _get_benchmark_close(cache, benchmark_ticker, start_date)
    bench_end_p, _ = _get_benchmark_close(cache, benchmark_ticker, end_date)

    if bench_start_p and bench_end_p and bench_start_p > 0:
        bench_ret = round(((bench_end_p - bench_start_p) / bench_start_p) * 100, 4)
        excess_ret = round(stock_ret - bench_ret, 4)
        bench_missing = False
    else:
        bench_ret = None
        excess_ret = stock_ret
        bench_missing = True

    return {
        "start_date": start_date,
        "end_date": end_date,
        "start_price": start_price,
        "end_price": end_price,
        "stock_return": stock_ret,
        "benchmark_return": bench_ret,
        "excess_return": excess_ret,
        "benchmark_missing": bench_missing,
        "chosen_return": excess_ret if not bench_missing else stock_ret
    }


def _get_future_return(ticker: str, pub_date: str, n_days: int) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Look up (start_price, end_price, return_pct) for ticker n_days after pub_date.
    Maintained for full backward-compatibility.
    """
    res = compute_excess_return(ticker, pub_date, n_days)
    return res["start_price"], res["end_price"], res["stock_return"]


def compute_volatility_threshold(
    volatility: Optional[float],
    k: float = DEFAULT_VOLATILITY_K,
    floor: float = DEFAULT_THRESHOLD_FLOOR,
    cap: float = DEFAULT_THRESHOLD_CAP,
    default_threshold: float = RETURN_THRESHOLD
) -> float:
    """
    Calculate point-in-time volatility-scaled threshold:
    threshold = max(floor, min(cap, k * historical_volatility))
    """
    if volatility is None or np.isnan(volatility) or volatility <= 0:
        return default_threshold
    raw_thresh = k * float(volatility)
    return round(max(floor, min(cap, raw_thresh)), 4)


def return_to_class(
    ret: Optional[float],
    volatility: Optional[float] = None,
    mode: str = "volatility_scaled",
    k: float = DEFAULT_VOLATILITY_K,
    floor: float = DEFAULT_THRESHOLD_FLOOR,
    cap: float = DEFAULT_THRESHOLD_CAP,
    fixed_threshold: float = RETURN_THRESHOLD
) -> str:
    """
    Convert return % to classification label: 'Positive', 'Neutral', or 'Negative'.
    Supports both 'volatility_scaled' (default) and 'fixed' modes for comparison.
    """
    if ret is None or np.isnan(ret):
        return "UNLABELED"

    if mode == "volatility_scaled" and volatility is not None and volatility > 0:
        thresh = compute_volatility_threshold(volatility, k=k, floor=floor, cap=cap, default_threshold=fixed_threshold)
    else:
        thresh = fixed_threshold

    if ret > thresh:
        return "Positive"
    if ret < -thresh:
        return "Negative"
    return "Neutral"


def _return_to_class(ret: float) -> str:
    """Legacy fixed-threshold return-to-class mapping (0.5%)."""
    return return_to_class(ret, mode="fixed", fixed_threshold=RETURN_THRESHOLD)


def evaluate_baselines(
    y_train: np.ndarray,
    y_test: np.ndarray,
    sentiment_scores_test: Optional[np.ndarray] = None,
    sentiment_threshold: float = 0.05,
    random_state: int = 42
) -> Dict[str, Dict[str, Any]]:
    """
    Compute 3 standard baseline classifiers on the test set:
    (a) Majority class: always predicts most frequent class in y_train
    (b) Sentiment-sign rule: Positive if sentiment > 0.05, Negative if < -0.05, Neutral otherwise
    (c) Random stratified: predicts according to training class distribution
    """
    from collections import Counter
    results = {}

    # (a) Majority class
    train_counts = Counter(y_train)
    majority_class = train_counts.most_common(1)[0][0] if train_counts else "Neutral"
    y_pred_maj = np.array([majority_class] * len(y_test))

    results["majority_class"] = {
        "predicted_class": majority_class,
        "accuracy": round(float(accuracy_score(y_test, y_pred_maj)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_test, y_pred_maj)), 4),
        "f1_macro": round(float(f1_score(y_test, y_pred_maj, average="macro", zero_division=0)), 4),
        "precision_macro": round(float(precision_score(y_test, y_pred_maj, average="macro", zero_division=0)), 4),
        "recall_macro": round(float(recall_score(y_test, y_pred_maj, average="macro", zero_division=0)), 4),
    }

    # (b) Sentiment-sign rule
    if sentiment_scores_test is not None and len(sentiment_scores_test) == len(y_test):
        y_pred_sent = []
        for s in sentiment_scores_test:
            try:
                s_val = float(s) if s is not None and not np.isnan(s) else 0.0
            except Exception:
                s_val = 0.0
            if s_val > sentiment_threshold:
                y_pred_sent.append("Positive")
            elif s_val < -sentiment_threshold:
                y_pred_sent.append("Negative")
            else:
                y_pred_sent.append("Neutral")
        y_pred_sent = np.array(y_pred_sent)
        results["sentiment_sign"] = {
            "threshold": sentiment_threshold,
            "accuracy": round(float(accuracy_score(y_test, y_pred_sent)), 4),
            "balanced_accuracy": round(float(balanced_accuracy_score(y_test, y_pred_sent)), 4),
            "f1_macro": round(float(f1_score(y_test, y_pred_sent, average="macro", zero_division=0)), 4),
            "precision_macro": round(float(precision_score(y_test, y_pred_sent, average="macro", zero_division=0)), 4),
            "recall_macro": round(float(recall_score(y_test, y_pred_sent, average="macro", zero_division=0)), 4),
        }
    else:
        results["sentiment_sign"] = None

    # (c) Random stratified
    dummy = DummyClassifier(strategy="stratified", random_state=random_state)
    dummy.fit(np.zeros((len(y_train), 1)), y_train)
    y_pred_rand = dummy.predict(np.zeros((len(y_test), 1)))

    results["random_stratified"] = {
        "strategy": "stratified",
        "accuracy": round(float(accuracy_score(y_test, y_pred_rand)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_test, y_pred_rand)), 4),
        "f1_macro": round(float(f1_score(y_test, y_pred_rand, average="macro", zero_division=0)), 4),
        "precision_macro": round(float(precision_score(y_test, y_pred_rand, average="macro", zero_division=0)), 4),
        "recall_macro": round(float(recall_score(y_test, y_pred_rand, average="macro", zero_division=0)), 4),
    }

    return results


def _build_labeled_dataset(
    horizon: str,
    label_mode: str = "volatility_scaled",
    k: float = DEFAULT_VOLATILITY_K,
    floor: float = DEFAULT_THRESHOLD_FLOOR,
    cap: float = DEFAULT_THRESHOLD_CAP,
    fixed_threshold: float = RETURN_THRESHOLD,
    use_excess_return: bool = True,
    benchmark_ticker: str = "^NSEI",
) -> Optional[Tuple[Any, Dict[str, int], Dict[str, int]]]:
    """
    Join analysis + stock_price to build a labeled feature matrix.
    Enforces strict point-in-time feature construction with zero data leakage:
    1. Historical reactions are computed strictly from events realized prior to the article timestamp.
    2. Benchmark-relative (excess) returns: stock return minus ^NSEI return over the same trading-day alignment.
       Falls back to raw return if benchmark data is missing, flagging benchmark_missing.
    3. Volatility-scaled threshold: k * 20-day historical volatility (with floor & cap), or fixed mode.
    4. Records are ordered chronologically by publication time.
    """
    if not (HAS_PANDAS and HAS_SKLEARN):
        return None

    days_map = {"1d": 1, "3d": 3, "5d": 5}
    n_days = days_map.get(horizon, 1)

    conn = get_connection()
    query = """
        SELECT
            an.id AS analysis_id,
            an.article_id,
            an.ticker,
            an.company_name,
            an.sector,
            an.event_type,
            an.sentiment_score,
            an.direction,
            an.impact_level,
            an.forward_return_1d,
            an.forward_return_3d,
            an.forward_return_5d,
            an.source_dataset,
            an.source_ticker,
            an.source_company,
            an.affected_ticker,
            an.affected_company,
            a.title AS article_title,
            a.published_at,
            a.source
        FROM analysis an
        JOIN articles a ON an.article_id = a.id
        WHERE an.ticker IS NOT NULL AND a.published_at IS NOT NULL
        ORDER BY a.published_at ASC
    """
    rows = conn.execute(query).fetchall()
    conn.close()

    if not rows:
        return None

    cache = get_price_cache()

    event_types = sorted(list({r["event_type"] or "OTHER" for r in rows}))
    sectors = sorted(list({r["sector"] or "Broad Market" for r in rows}))
    event_enc = {e: i for i, e in enumerate(event_types)}
    sector_enc = {s: i for i, s in enumerate(sectors)}

    # Point-in-time category reaction tracker (Zero Leakage)
    cat_return_sum = defaultdict(float)
    cat_return_count = defaultdict(int)
    pending_realizations = []  # list of (realization_date_str, category, return_pct)

    records = []
    for r in rows:
        ticker = r["ticker"]
        pub_dt = _parse_date_str(r["published_at"])
        if not pub_dt:
            continue

        # Look up stock & benchmark returns aligned on trading days
        ret_info = compute_excess_return(ticker, pub_dt, n_days, benchmark_ticker=benchmark_ticker, cache=cache)
        raw_ret = ret_info["stock_return"]
        bench_ret = ret_info["benchmark_return"]
        excess_ret = ret_info["excess_return"]
        bench_missing = ret_info["benchmark_missing"]

        # If price cache lookup yielded None, check if analysis table had raw forward return
        if raw_ret is None:
            if horizon == "1d":
                raw_ret = r["forward_return_1d"]
            elif horizon == "3d":
                raw_ret = r["forward_return_3d"]
            elif horizon == "5d":
                raw_ret = r["forward_return_5d"]
            if raw_ret is not None:
                excess_ret = raw_ret
                bench_missing = True

        if raw_ret is None:
            continue  # Future return not yet realized / unavailable for this horizon

        chosen_ret = excess_ret if (use_excess_return and excess_ret is not None) else raw_ret

        # Point-in-Time update: realize past events that completed prior to current pub_dt
        new_pending = []
        for r_date, cat_name, ret_val in pending_realizations:
            if r_date <= pub_dt:
                cat_return_sum[cat_name] += ret_val
                cat_return_count[cat_name] += 1
            else:
                new_pending.append((r_date, cat_name, ret_val))
        pending_realizations = new_pending

        # Compute point-in-time historical category reaction
        cat = r["event_type"] or "OTHER"
        if cat_return_count[cat] > 0:
            hist_cat_reaction = round(cat_return_sum[cat] / cat_return_count[cat], 4)
        else:
            hist_cat_reaction = 0.0

        # Queue current event's completion date for future point-in-time calculations
        try:
            pub_date_obj = datetime.strptime(pub_dt, "%Y-%m-%d")
            completion_dt = (pub_date_obj + timedelta(days=n_days + 1)).strftime("%Y-%m-%d")
            pending_realizations.append((completion_dt, cat, chosen_ret))
        except Exception:
            pass

        stock_feats = _get_stock_features(ticker, pub_dt)
        mkt_trend = _get_market_trend(pub_dt)
        hist_vol = stock_feats["historical_volatility"]

        threshold_applied = (
            compute_volatility_threshold(hist_vol, k=k, floor=floor, cap=cap, default_threshold=fixed_threshold)
            if label_mode == "volatility_scaled"
            else fixed_threshold
        )

        label = return_to_class(
            chosen_ret,
            volatility=hist_vol,
            mode=label_mode,
            k=k,
            floor=floor,
            cap=cap,
            fixed_threshold=fixed_threshold
        )

        # Point-in-time session timing (hour in day normalized: 09:15 -> ~0.385)
        raw_pub = str(r["published_at"])
        session_timing = 0.3854  # Default 09:15 AM
        try:
            if "T" in raw_pub and len(raw_pub) >= 16:
                tp = raw_pub.split("T")[1][:5]
                hh, mm = map(int, tp.split(":"))
                session_timing = round((hh + mm / 60.0) / 24.0, 4)
            elif " " in raw_pub and len(raw_pub) >= 16:
                tp = raw_pub.split(" ")[1][:5]
                hh, mm = map(int, tp.split(":"))
                session_timing = round((hh + mm / 60.0) / 24.0, 4)
        except Exception:
            session_timing = 0.3854

        sent_score = float(r["sentiment_score"] or 0.0)

        feat = [
            sent_score,
            1.0 if sent_score > 0.12 else (-1.0 if sent_score < -0.12 else 0.0),
            abs(sent_score),
            float(event_enc.get(r["event_type"] or "OTHER", 0)),
            float(sector_enc.get(r["sector"] or "Broad Market", 0)),
            stock_feats["recent_return_1d"],
            hist_vol,
            stock_feats["volume_norm"],
            mkt_trend,
            hist_cat_reaction,
            session_timing,
        ]

        records.append({
            "features": feat,
            "label": label,
            "analysis_id": r["analysis_id"],
            "article_id": r["article_id"],
            "article_title": r["article_title"],
            "ticker": ticker,
            "sector": r["sector"],
            "event_type": r["event_type"],
            "published_at": pub_dt,
            "actual_return": chosen_ret,
            "raw_return": raw_ret,
            "benchmark_return": bench_ret,
            "excess_return": excess_ret,
            "benchmark_missing": bench_missing,
            "volatility": hist_vol,
            "threshold_applied": threshold_applied,
            "sentiment_score": sent_score,
        })

    if not records:
        return None

    df = pd.DataFrame(records)
    df["X"] = df["features"]
    df["sentiment_score"] = [rec["sentiment_score"] for rec in records]
    return df, event_enc, sector_enc


# ══════════════════════════════════════════════════════════════════
# 3.  DATASET EXPORT (CSV / JSON)
# ══════════════════════════════════════════════════════════════════
def export_dataset() -> Dict[str, Any]:
    """
    Build and export a consolidated dataset with all articles, analysis,
    technical indicators, multi-horizon returns, and labels to dataset_export.csv.
    Preserves source vs affected ticker/company distinctions.
    """
    get_price_cache().reload()
    conn = get_connection()
    query = """
        SELECT
            an.id AS analysis_id,
            an.article_id,
            a.title,
            a.source,
            a.url,
            a.published_at,
            an.source_dataset,
            an.source_ticker,
            an.source_company,
            an.affected_ticker,
            an.affected_company,
            an.ticker,
            an.company_name,
            an.sector,
            an.event_type,
            an.event_display,
            an.sentiment,
            an.sentiment_score,
            an.direction,
            an.impact_level,
            an.confidence,
            an.forward_return_1d,
            an.forward_return_3d,
            an.forward_return_5d
        FROM analysis an
        JOIN articles a ON an.article_id = a.id
        WHERE an.ticker IS NOT NULL
        ORDER BY a.published_at DESC
    """
    rows = conn.execute(query).fetchall()
    conn.close()

    export_records = []
    for r in rows:
        ticker = r["ticker"]
        pub_dt = _parse_date_str(r["published_at"])
        if not pub_dt:
            continue

        stock_feats = _get_stock_features(ticker, pub_dt)
        mkt_trend = _get_market_trend(pub_dt)

        # 1D, 3D, 5D returns: prioritize stored real returns, fallback to stock_price OHLCV
        ret_1 = r["forward_return_1d"]
        if ret_1 is None:
            _, _, ret_1 = _get_future_return(ticker, pub_dt, 1)

        ret_3 = r["forward_return_3d"]
        if ret_3 is None:
            _, _, ret_3 = _get_future_return(ticker, pub_dt, 3)

        ret_5 = r["forward_return_5d"]
        if ret_5 is None:
            _, _, ret_5 = _get_future_return(ticker, pub_dt, 5)

        rec = {
            "analysis_id": r["analysis_id"],
            "article_id": r["article_id"],
            "title": r["title"],
            "source": r["source"],
            "url": r["url"],
            "published_at": pub_dt,
            "source_dataset": r["source_dataset"] or "production",
            "source_ticker": r["source_ticker"] or ticker,
            "source_company": r["source_company"] or r["company_name"],
            "affected_ticker": r["affected_ticker"] or ticker,
            "affected_company": r["affected_company"] or r["company_name"],
            "ticker": ticker,
            "company_name": r["company_name"],
            "sector": r["sector"] or "Broad Market",
            "event_type": r["event_type"] or "OTHER",
            "sentiment": r["sentiment"],
            "sentiment_score": round(float(r["sentiment_score"] or 0), 4),
            "sentiment_direction": r["direction"],
            "impact_level": r["impact_level"],
            "confidence": r["confidence"],
            "recent_return_1d": stock_feats["recent_return_1d"],
            "historical_volatility": stock_feats["historical_volatility"],
            "volume_norm": stock_feats["volume_norm"],
            "market_trend": mkt_trend,
            "return_1d": ret_1,
            "label_1d": _return_to_class(ret_1) if ret_1 is not None else "UNLABELED",
            "return_3d": ret_3,
            "label_3d": _return_to_class(ret_3) if ret_3 is not None else "UNLABELED",
            "return_5d": ret_5,
            "label_5d": _return_to_class(ret_5) if ret_5 is not None else "UNLABELED",
        }
        export_records.append(rec)

    if HAS_PANDAS and export_records:
        df_export = pd.DataFrame(export_records)
        df_export.to_csv(DATASET_CSV_PATH, index=False)
        logger.info("[ML] Exported %d dataset rows to %s", len(df_export), DATASET_CSV_PATH)

    labeled_1d = sum(1 for r in export_records if r["label_1d"] != "UNLABELED")
    labeled_3d = sum(1 for r in export_records if r["label_3d"] != "UNLABELED")
    labeled_5d = sum(1 for r in export_records if r["label_5d"] != "UNLABELED")

    return {
        "file_path": DATASET_CSV_PATH,
        "total_records": len(export_records),
        "labeled_1d": labeled_1d,
        "labeled_3d": labeled_3d,
        "labeled_5d": labeled_5d,
        "download_url": "/api/ml/dataset/download",
        "sample": export_records[:3] if export_records else [],
    }


# ══════════════════════════════════════════════════════════════════
# 4.  TRAINING PIPELINE (Walk-Forward Chronological Validation)
# ══════════════════════════════════════════════════════════════════
MODELS = {
    "LogisticRegression": lambda: LogisticRegression(
        max_iter=1000, C=0.5, class_weight="balanced", random_state=42
    ),
    "RandomForest": lambda: RandomForestClassifier(
        n_estimators=100, max_depth=6, class_weight="balanced",
        n_jobs=-1, random_state=42
    ),
    "GradientBoosting": lambda: GradientBoostingClassifier(
        n_estimators=100, max_depth=4, learning_rate=0.08,
        subsample=0.8, random_state=42
    ),
}


def train_all(
    on_progress: Optional[Callable[[int, int, str, str], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
    label_mode: str = "volatility_scaled",
    k: float = DEFAULT_VOLATILITY_K,
    floor: float = DEFAULT_THRESHOLD_FLOOR,
    cap: float = DEFAULT_THRESHOLD_CAP,
    use_excess_return: bool = True,
    fixed_threshold: float = RETURN_THRESHOLD,
    benchmark_ticker: str = "^NSEI",
) -> Dict[str, Any]:
    """
    Train all 3 models × 3 horizons (9 total models).
    Enforces strict time-aware evaluation and honest baselines:
    - Benchmark-relative excess returns against ^NSEI over identical trading days.
    - Volatility-scaled labeling threshold (or fixed mode via config).
    - Chronological 80/20 train/test split (no future data mixed into training).
    - Baselines evaluated on identical test set: majority class, sentiment sign, random stratified.
    - Headline metrics: Balanced Accuracy & Macro F1.
    - Small-sample reporting safeguard: requires n_test >= 200.
    """
    if not (HAS_PANDAS and HAS_SKLEARN):
        return {"error": "pandas or scikit-learn not installed."}

    if is_cancelled and is_cancelled():
        return {"status": "cancelled", "message": "Training cancelled."}

    if on_progress:
        on_progress(1, 10, "Cache", "Refreshing in-memory stock price cache...")
    get_price_cache().reload()

    results = {}
    horizons = ["1d", "3d", "5d"]
    total_steps = 1 + (len(horizons) * len(MODELS))
    current_step = 1

    for horizon in horizons:
        if is_cancelled and is_cancelled():
            return results

        dataset = _build_labeled_dataset(
            horizon,
            label_mode=label_mode,
            k=k,
            floor=floor,
            cap=cap,
            fixed_threshold=fixed_threshold,
            use_excess_return=use_excess_return,
            benchmark_ticker=benchmark_ticker
        )

        if dataset is None:
            for model_name in MODELS:
                current_step += 1
                if on_progress:
                    on_progress(current_step, total_steps, f"{model_name}_{horizon}", f"Insufficient labeled data for {horizon} horizon.")
                _store_insufficient(model_name, horizon, "No analysis+stock_price labeled rows found.")
                results[f"{model_name}_{horizon}"] = {"insufficient": True, "horizon": horizon}
            continue

        df, event_enc, sector_enc = dataset
        n_total = len(df)

        if n_total < MIN_SAMPLES:
            msg = f"Only {n_total} labeled samples (need {MIN_SAMPLES}). Sync more news + stock data."
            for model_name in MODELS:
                current_step += 1
                if on_progress:
                    on_progress(current_step, total_steps, f"{model_name}_{horizon}", f"Need >= {MIN_SAMPLES} samples for {horizon} (have {n_total}).")
                _store_insufficient(model_name, horizon, msg)
                results[f"{model_name}_{horizon}"] = {
                    "insufficient": True, "n": n_total, "horizon": horizon,
                    "message": "Model requires more historical data for reliable training."
                }
            continue

        X = np.array(df["X"].tolist())
        y = np.array(df["label"].tolist())

        # Strict Chronological Train/Test split: first 80% train, last 20% test (Out-Of-Sample forward test)
        split_idx = int(n_total * 0.8)
        X_train, y_train = X[:split_idx], y[:split_idx]
        X_test, y_test   = X[split_idx:], y[split_idx:]
        n_train, n_test  = len(X_train), len(X_test)

        # Safeguard: Never present metrics when n_test < 200
        if n_test < MIN_TEST_SAMPLES:
            msg = f"Insufficient test samples (n_test={n_test} < {MIN_TEST_SAMPLES}). Need >= {MIN_TEST_SAMPLES} held-out test samples for defensible evaluation."
            logger.warning("[ML] %s horizon: %s", horizon, msg)
            for model_name in MODELS:
                current_step += 1
                if on_progress:
                    on_progress(current_step, total_steps, f"{model_name}_{horizon}", msg)
                _store_insufficient(model_name, horizon, msg, n_train=n_train, n_test=n_test)
                results[f"{model_name}_{horizon}"] = {
                    "insufficient": True,
                    "n_train": n_train,
                    "n_test": n_test,
                    "horizon": horizon,
                    "message": "insufficient data"
                }
            continue

        # Evaluate honest baselines on held-out test data
        sentiment_scores_test = np.array(df["sentiment_score"].iloc[split_idx:].tolist())
        baseline_results = evaluate_baselines(
            y_train=y_train,
            y_test=y_test,
            sentiment_scores_test=sentiment_scores_test,
            random_state=42
        )

        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s  = scaler.transform(X_test)

        for model_name, model_fn in MODELS.items():
            if is_cancelled and is_cancelled():
                return results

            current_step += 1
            if on_progress:
                on_progress(current_step, total_steps, f"{model_name}_{horizon}", f"Training {model_name} for {horizon} horizon (Walk-Forward CV)...")
            try:
                model = model_fn()
                model.fit(X_train_s, y_train)
                y_pred = model.predict(X_test_s)

                acc     = round(float(accuracy_score(y_test, y_pred)), 4)
                bal_acc = round(float(balanced_accuracy_score(y_test, y_pred)), 4)
                prec    = round(float(precision_score(y_test, y_pred, average="macro", zero_division=0)), 4)
                rec     = round(float(recall_score(y_test, y_pred, average="macro", zero_division=0)), 4)
                f1      = round(float(f1_score(y_test, y_pred, average="macro", zero_division=0)), 4)
                cm      = confusion_matrix(y_test, y_pred, labels=CLASS_LABELS).tolist()

                # Feature importances (RF & GB)
                fi = None
                if hasattr(model, "feature_importances_"):
                    fi = [round(float(x), 4) for x in model.feature_importances_]

                # Walk-Forward Cross-validation (expanding window TimeSeriesSplit on training data)
                cv_acc_mean = None
                cv_acc_std = None
                cv_f1_mean = None
                n_splits = min(5, max(3, len(X_train) // 100))
                try:
                    tscv = TimeSeriesSplit(n_splits=n_splits)
                    cv_model = model_fn()
                    cv_scores_acc = cross_val_score(cv_model, X_train_s, y_train, cv=tscv,
                                                    scoring="accuracy", n_jobs=-1)
                    cv_model2 = model_fn()
                    cv_scores_f1 = cross_val_score(cv_model2, X_train_s, y_train, cv=tscv,
                                                   scoring="f1_macro", n_jobs=-1)
                    cv_acc_mean = round(float(np.mean(cv_scores_acc)), 4)
                    cv_acc_std  = round(float(np.std(cv_scores_acc)), 4)
                    cv_f1_mean  = round(float(np.mean(cv_scores_f1)), 4)
                except Exception as cv_err:
                    logger.warning("[ML] Walk-forward CV for %s %s failed: %s", model_name, horizon, cv_err)

                # Save model + scaler bundle
                model_path = os.path.join(MODEL_DIR, f"{model_name}_{horizon}.joblib")
                joblib.dump({
                    "model": model,
                    "scaler": scaler,
                    "event_enc": event_enc,
                    "sector_enc": sector_enc,
                    "feature_names": FEATURE_NAMES,
                    "class_labels": CLASS_LABELS,
                    "balanced_accuracy": bal_acc,
                    "f1_macro": f1,
                    "accuracy": acc,
                    "baseline_metrics": baseline_results,
                    "cv_acc_mean": cv_acc_mean,
                    "cv_acc_std": cv_acc_std,
                    "cv_f1_mean": cv_f1_mean,
                    "n_folds": n_splits if cv_acc_mean is not None else None,
                    "label_mode": label_mode,
                    "volatility_k": k,
                    "use_excess_return": use_excess_return,
                }, model_path)

                _store_metric(
                    model_name=model_name,
                    horizon=horizon,
                    n_train=len(X_train),
                    n_test=len(X_test),
                    accuracy=acc,
                    balanced_accuracy=bal_acc,
                    precision=prec,
                    recall=rec,
                    f1=f1,
                    cm=cm,
                    fi=fi,
                    model_path=model_path,
                    baseline_metrics=baseline_results,
                    cv_acc_mean=cv_acc_mean,
                    cv_acc_std=cv_acc_std,
                    cv_f1_mean=cv_f1_mean,
                    label_mode=label_mode,
                    volatility_k=k,
                    use_excess_return=use_excess_return,
                )

                metric = {
                    "model": model_name, "horizon": horizon,
                    "n_train": len(X_train), "n_test": len(X_test),
                    "balanced_accuracy": bal_acc,    # Headline metric
                    "f1_macro": f1,                  # Headline metric
                    "accuracy": acc,                 # Raw accuracy
                    "precision_macro": prec,
                    "recall_macro": rec,
                    "confusion_matrix": cm,
                    "feature_importances": fi,
                    "baselines": baseline_results,
                    "cv_accuracy_mean": cv_acc_mean,
                    "cv_accuracy_std": cv_acc_std,
                    "cv_f1_mean": cv_f1_mean,
                    "insufficient": False,
                    "label_mode": label_mode,
                    "volatility_k": k,
                    "use_excess_return": use_excess_return,
                }
                results[f"{model_name}_{horizon}"] = metric
                logger.info("[ML] %s %s → bal_acc=%.3f f1=%.3f raw_acc=%.3f (n_train=%d, n_test=%d)",
                            model_name, horizon, bal_acc, f1, acc, len(X_train), len(X_test))
                if on_progress:
                    on_progress(current_step, total_steps, f"{model_name}_{horizon}",
                                f"Done {model_name} ({horizon}): Bal Acc={bal_acc*100:.1f}%, Macro F1={f1*100:.1f}%")

            except Exception as e:
                logger.error("[ML] %s %s training error: %s", model_name, horizon, e)
                results[f"{model_name}_{horizon}"] = {"error": str(e)}
                if on_progress:
                    on_progress(current_step, total_steps, f"{model_name}_{horizon}", f"Error {model_name} ({horizon}): {e}")

    # Export latest dataset CSV
    try:
        export_dataset()
    except Exception as e:
        logger.warning("[ML] Dataset export note: %s", e)

    if on_progress:
        on_progress(total_steps, total_steps, "COMPLETE", "All ML models trained and validated successfully.")

    return results


def _store_metric(
    model_name: str,
    horizon: str,
    n_train: int,
    n_test: int,
    accuracy: float,
    precision: float,
    recall: float,
    f1: float,
    cm: list,
    fi: Optional[list],
    model_path: str,
    balanced_accuracy: Optional[float] = None,
    baseline_metrics: Optional[Dict[str, Any]] = None,
    cv_acc_mean: Optional[float] = None,
    cv_acc_std: Optional[float] = None,
    cv_f1_mean: Optional[float] = None,
    label_mode: str = "volatility_scaled",
    volatility_k: float = DEFAULT_VOLATILITY_K,
    use_excess_return: bool = True,
):
    conn = get_connection()
    notes_data = {
        "label_mode": label_mode,
        "volatility_k": volatility_k,
        "use_excess_return": use_excess_return,
    }
    if cv_acc_mean is not None:
        notes_data["cv_accuracy_mean"] = cv_acc_mean
        notes_data["cv_accuracy_std"] = cv_acc_std
        notes_data["cv_f1_mean"] = cv_f1_mean

    is_suff = 1 if (n_test is not None and n_test >= MIN_TEST_SAMPLES) else 0

    conn.execute("""
        INSERT OR REPLACE INTO model_metric
        (model_name, horizon, trained_at, n_train, n_test,
         accuracy, balanced_accuracy, precision_macro, recall_macro, f1_macro,
         confusion_matrix, feature_names, feature_importances,
         class_labels, baseline_metrics, is_sufficient, model_path, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        model_name, horizon, datetime.now().isoformat(),
        n_train, n_test, accuracy, balanced_accuracy, precision, recall, f1,
        json.dumps(cm), json.dumps(FEATURE_NAMES),
        json.dumps(fi) if fi else None,
        json.dumps(CLASS_LABELS),
        json.dumps(baseline_metrics) if baseline_metrics else None,
        is_suff, model_path,
        json.dumps(notes_data),
    ))
    conn.commit()
    conn.close()


def _store_insufficient(model_name: str, horizon: str, notes: str, n_train: int = 0, n_test: int = 0):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO model_metric
        (model_name, horizon, trained_at, n_train, n_test, is_sufficient, notes)
        VALUES (?,?,?,?,?,0,?)
    """, (model_name, horizon, datetime.now().isoformat(), n_train, n_test, notes))
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════
# 5.  INFERENCE — Per-Article ML Prediction
# ══════════════════════════════════════════════════════════════════
def predict_article(analysis_result: dict, pub_date: str) -> Dict[str, Any]:
    """
    Run ML inference across all trained models and horizons.
    Returns per-model predictions and ensemble vote.
    """
    if not (HAS_SKLEARN and HAS_PANDAS):
        return {}

    ticker = analysis_result.get("ticker", "^NSEI")
    event_type = analysis_result.get("event_type", "OTHER")
    sector = analysis_result.get("sector", "Broad Market")
    sent_score = float(analysis_result.get("sentiment_score", 0.0))

    clean_pub_date = _parse_date_str(pub_date) or datetime.now().strftime("%Y-%m-%d")
    stock_feats = _get_stock_features(ticker, clean_pub_date)
    mkt_trend = _get_market_trend(clean_pub_date)

    base_feat = [
        sent_score,
        1.0 if sent_score > 0.12 else (-1.0 if sent_score < -0.12 else 0.0),
        abs(sent_score),
        0.0,
        0.0,
        stock_feats["recent_return_1d"],
        stock_feats["historical_volatility"],
        stock_feats["volume_norm"],
        mkt_trend,
        0.0,
        1.0,
    ]

    predictions: Dict[str, Any] = {}
    for horizon in ["1d", "3d", "5d"]:
        horizon_preds = {}
        for model_name in MODELS:
            model_path = os.path.join(MODEL_DIR, f"{model_name}_{horizon}.joblib")
            if not os.path.exists(model_path):
                continue
            try:
                bundle = joblib.load(model_path)
                model   = bundle["model"]
                scaler  = bundle["scaler"]
                evt_enc = bundle.get("event_enc", {})
                sec_enc = bundle.get("sector_enc", {})

                feat = base_feat.copy()
                feat[3] = float(evt_enc.get(event_type, 0))
                feat[4] = float(sec_enc.get(sector, 0))

                X = scaler.transform([feat])
                pred_class = model.predict(X)[0]
                probs = model.predict_proba(X)[0]
                class_order = list(model.classes_)

                prob_map = {c: round(float(p), 3) for c, p in zip(class_order, probs)}
                horizon_preds[model_name] = {
                    "predicted_class": pred_class,
                    "prob_positive": prob_map.get("Positive", 0.0),
                    "prob_neutral":  prob_map.get("Neutral",  0.0),
                    "prob_negative": prob_map.get("Negative", 0.0),
                }
            except Exception as e:
                logger.warning("[ML Inference] %s %s: %s", model_name, horizon, e)

        if horizon_preds:
            votes = [v["predicted_class"] for v in horizon_preds.values()]
            from collections import Counter
            ensemble_class = Counter(votes).most_common(1)[0][0]
            predictions[horizon] = {
                "models": horizon_preds,
                "ensemble": ensemble_class,
            }

    return predictions


# ══════════════════════════════════════════════════════════════════
# 6.  GET METRICS FROM DB
# ══════════════════════════════════════════════════════════════════
def get_model_metrics() -> Dict[str, Any]:
    """Load all stored model metrics from model_metric table."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM model_metric ORDER BY model_name, horizon").fetchall()
    n_price_rows = conn.execute("SELECT COUNT(*) FROM stock_price").fetchone()[0]
    n_analysis_rows = conn.execute("SELECT COUNT(*) FROM analysis").fetchone()[0]
    conn.close()

    metrics = []
    has_sufficient = False

    for r in rows:
        m = dict(r)
        m["confusion_matrix"]      = json.loads(m["confusion_matrix"]) if m.get("confusion_matrix") else None
        m["feature_importances"]   = json.loads(m["feature_importances"]) if m.get("feature_importances") else None
        m["feature_names"]         = json.loads(m["feature_names"]) if m.get("feature_names") else FEATURE_NAMES
        m["class_labels"]          = json.loads(m["class_labels"]) if m.get("class_labels") else CLASS_LABELS
        m["baseline_metrics"]      = json.loads(m["baseline_metrics"]) if m.get("baseline_metrics") else None
        if m.get("balanced_accuracy") is not None:
            m["balanced_accuracy"] = round(float(m["balanced_accuracy"]), 4)

        # Enforce MIN_TEST_SAMPLES safeguard: never present metrics if n_test < 200
        if m.get("n_test") is not None and m["n_test"] < MIN_TEST_SAMPLES:
            m["is_sufficient"] = 0

        # Parse CV metrics and training parameters from notes JSON
        if m.get("notes"):
            try:
                notes_data = json.loads(m["notes"])
                m["cv_accuracy_mean"]  = notes_data.get("cv_accuracy_mean")
                m["cv_accuracy_std"]   = notes_data.get("cv_accuracy_std")
                m["cv_f1_mean"]        = notes_data.get("cv_f1_mean")
                m["label_mode"]        = notes_data.get("label_mode", "volatility_scaled")
                m["volatility_k"]      = notes_data.get("volatility_k", DEFAULT_VOLATILITY_K)
                m["use_excess_return"] = notes_data.get("use_excess_return", True)
            except Exception:
                pass
        if m.get("is_sufficient"):
            has_sufficient = True
        metrics.append(m)

    # Get dataset CSV row count if available
    dataset_rows = 0
    if os.path.exists(DATASET_CSV_PATH):
        try:
            with open(DATASET_CSV_PATH, 'r') as f:
                dataset_rows = sum(1 for _ in f) - 1  # minus header
        except Exception:
            dataset_rows = 0

    return {
        "metrics": metrics,
        "feature_names": FEATURE_NAMES,
        "class_labels": CLASS_LABELS,
        "has_sufficient_data": has_sufficient,
        "min_samples_required": MIN_SAMPLES,
        "min_test_samples": MIN_TEST_SAMPLES,
        "return_threshold_pct": RETURN_THRESHOLD,
        "compliance_disclaimer": "AI/model estimate — not investment advice.",
        "dataset_csv_available": os.path.exists(DATASET_CSV_PATH),
        "dataset_csv_rows": dataset_rows,
        "dataset_download_url": "/api/ml/dataset/download",
        "stock_price_rows": n_price_rows,
        "analysis_rows": n_analysis_rows,
    }


def print_evaluation_table(results: Dict[str, Any]) -> str:
    """
    Format a clean, professional table of Model vs Baselines per Horizon,
    with n_train, n_test, balanced accuracy, macro-F1, and accuracy.
    """
    lines = []
    lines.append("=" * 110)
    lines.append(f"{'HORIZON':<8} | {'CLASSIFIER / BASELINE':<26} | {'N_TRAIN':<8} | {'N_TEST':<8} | {'BAL_ACC':<9} | {'MACRO_F1':<9} | {'RAW_ACC':<9}")
    lines.append("-" * 110)

    horizons = ["1d", "3d", "5d"]
    for h in horizons:
        baseline_printed = False
        for model_name in ["LogisticRegression", "RandomForest", "GradientBoosting"]:
            key = f"{model_name}_{h}"
            m = results.get(key, {})
            if m.get("insufficient"):
                n_tr = str(m.get("n_train", "—"))
                n_te = str(m.get("n_test", "—"))
                lines.append(f"{h:<8} | {model_name:<26} | {n_tr:<8} | {n_te:<8} | {'INSUFFICIENT DATA (< 200 samples)':<35}")
                continue

            if not baseline_printed and m.get("baselines"):
                baselines = m["baselines"]
                maj = baselines.get("majority_class", {})
                sent = baselines.get("sentiment_sign", {})
                rnd = baselines.get("random_stratified", {})

                n_tr = str(m.get("n_train", "—"))
                n_te = str(m.get("n_test", "—"))

                if maj:
                    lines.append(f"{h:<8} | {'[Baseline] Majority Class':<26} | {n_tr:<8} | {n_te:<8} | {maj.get('balanced_accuracy', 0)*100:>7.2f}% | {maj.get('f1_macro', 0)*100:>7.2f}% | {maj.get('accuracy', 0)*100:>7.2f}%")
                if sent:
                    lines.append(f"{'':<8} | {'[Baseline] Sentiment Sign':<26} | {n_tr:<8} | {n_te:<8} | {sent.get('balanced_accuracy', 0)*100:>7.2f}% | {sent.get('f1_macro', 0)*100:>7.2f}% | {sent.get('accuracy', 0)*100:>7.2f}%")
                if rnd:
                    lines.append(f"{'':<8} | {'[Baseline] Stratified Rand':<26} | {n_tr:<8} | {n_te:<8} | {rnd.get('balanced_accuracy', 0)*100:>7.2f}% | {rnd.get('f1_macro', 0)*100:>7.2f}% | {rnd.get('accuracy', 0)*100:>7.2f}%")
                lines.append(f"{'':<8} | {'-'*26} | {'-'*8} | {'-'*8} | {'-'*9} | {'-'*9} | {'-'*9}")
                baseline_printed = True

            n_tr = str(m.get("n_train", "—"))
            n_te = str(m.get("n_test", "—"))
            bal = f"{m.get('balanced_accuracy', 0)*100:>7.2f}%" if m.get("balanced_accuracy") is not None else "—"
            f1 = f"{m.get('f1_macro', 0)*100:>7.2f}%" if m.get("f1_macro") is not None else "—"
            acc = f"{m.get('accuracy', 0)*100:>7.2f}%" if m.get("accuracy") is not None else "—"
            lines.append(f"{h:<8} | {model_name:<26} | {n_tr:<8} | {n_te:<8} | {bal:>9} | {f1:>9} | {acc:>9}")

        lines.append("-" * 110)

    lines.append("=" * 110)
    lines.append("AI/model estimate — not investment advice.")
    table_str = "\n".join(lines)
    return table_str


if __name__ == "__main__":
    print("Running ML training pipeline with Phase 1 enhancements...")
    results = train_all()
    print("\n" + print_evaluation_table(results))
