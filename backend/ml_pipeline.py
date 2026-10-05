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
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score,
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

MIN_SAMPLES = 10            # Minimum labeled samples per horizon for training (supports realistic small-sample bootstrapping)
RETURN_THRESHOLD = 0.5      # % move threshold for Positive/Negative class

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
                return round(((c_now - c_5ago) / c_5ago) * 100, 4)
    return 0.0


# ══════════════════════════════════════════════════════════════════
# 2.  LABEL BUILDER & FUTURE RETURN
# ══════════════════════════════════════════════════════════════════
def _return_to_class(ret: float) -> str:
    if ret > RETURN_THRESHOLD:
        return "Positive"
    if ret < -RETURN_THRESHOLD:
        return "Negative"
    return "Neutral"


def _get_future_return(ticker: str, pub_date: str, n_days: int) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Look up (start_price, end_price, return_pct) for ticker n_days after pub_date.
    Uses calendar buffer to accommodate weekends & market holidays.
    """
    cache = get_price_cache()
    entries = cache.prices_by_ticker.get(ticker, [])
    if not entries:
        return None, None, None

    # Start price: on or first trading day after pub_date
    start_entries = [e for e in entries if e[0] >= pub_date]
    if not start_entries:
        return None, None, None
    start_date, start_price, _ = start_entries[0]
    if start_price <= 0:
        return None, None, None

    # Target date window: [pub_date + n_days, pub_date + n_days + 4]
    try:
        ref_dt = datetime.strptime(pub_date, "%Y-%m-%d")
        min_target = (ref_dt + timedelta(days=n_days)).strftime("%Y-%m-%d")
        max_target = (ref_dt + timedelta(days=n_days + 4)).strftime("%Y-%m-%d")
    except ValueError:
        return None, None, None

    end_entries = [e for e in entries if min_target <= e[0] <= max_target]
    if not end_entries:
        return None, None, None

    end_date, end_price, _ = end_entries[0]
    if end_price <= 0:
        return None, None, None

    ret = ((end_price - start_price) / start_price) * 100
    return start_price, end_price, round(ret, 4)


def _build_labeled_dataset(horizon: str) -> Optional[Tuple[Any, Dict[str, int], Dict[str, int]]]:
    """
    Join analysis + stock_price to build a labeled feature matrix.
    Enforces strict point-in-time feature construction with zero data leakage:
    1. Historical reactions are computed strictly from events realized prior to the article timestamp.
    2. Recency/session timing is strictly based on the publication timestamp without wall-clock bias.
    3. Records are ordered chronologically by publication time.
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

    event_types = sorted(list({r["event_type"] or "OTHER" for r in rows}))
    sectors = sorted(list({r["sector"] or "Broad Market" for r in rows}))
    event_enc = {e: i for i, e in enumerate(event_types)}
    sector_enc = {s: i for i, s in enumerate(sectors)}

    # Point-in-time category reaction tracker (Zero Leakage)
    # Only events whose future return period completed on or before current pub_dt are added
    cat_return_sum = defaultdict(float)
    cat_return_count = defaultdict(int)
    pending_realizations = []  # list of (realization_date_str, category, return_pct)

    records = []
    for r in rows:
        ticker = r["ticker"]
        pub_dt = _parse_date_str(r["published_at"])
        if not pub_dt:
            continue

        # Determine actual future return for the specified horizon
        actual_ret = None
        if horizon == "1d":
            actual_ret = r["forward_return_1d"]
        elif horizon == "3d":
            actual_ret = r["forward_return_3d"]
        elif horizon == "5d":
            actual_ret = r["forward_return_5d"]

        # If not already present in column, attempt lookup in stock_price OHLCV
        if actual_ret is None:
            _, _, actual_ret = _get_future_return(ticker, pub_dt, n_days)

        if actual_ret is None:
            continue  # Future return not yet realized / unavailable for this horizon

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
            pending_realizations.append((completion_dt, cat, actual_ret))
        except Exception:
            pass

        label = _return_to_class(actual_ret)
        stock_feats = _get_stock_features(ticker, pub_dt)
        mkt_trend = _get_market_trend(pub_dt)

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
            stock_feats["historical_volatility"],
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
            "actual_return": actual_ret,
        })

    if not records:
        return None

    df = pd.DataFrame(records)
    df["X"] = df["features"]
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
    is_cancelled: Optional[Callable[[], bool]] = None
) -> Dict[str, Any]:
    """
    Train all 3 models × 3 horizons (9 total models).
    Enforces strict time-aware evaluation:
    - Chronological 80/20 train/test split (no future data mixed into training).
    - Walk-Forward Expanding-Window TimeSeriesSplit on training data.
    - True out-of-sample forward evaluation on held-out test data.
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

        dataset = _build_labeled_dataset(horizon)
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

                acc  = round(float(accuracy_score(y_test, y_pred)), 4)
                prec = round(float(precision_score(y_test, y_pred, average="macro", zero_division=0)), 4)
                rec  = round(float(recall_score(y_test, y_pred, average="macro", zero_division=0)), 4)
                f1   = round(float(f1_score(y_test, y_pred, average="macro", zero_division=0)), 4)
                cm   = confusion_matrix(y_test, y_pred, labels=CLASS_LABELS).tolist()

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
                    "cv_acc_mean": cv_acc_mean,
                    "cv_acc_std": cv_acc_std,
                    "cv_f1_mean": cv_f1_mean,
                    "n_folds": n_splits if cv_acc_mean is not None else None,
                }, model_path)

                _store_metric(
                    model_name=model_name, horizon=horizon,
                    n_train=len(X_train), n_test=len(X_test),
                    accuracy=acc, precision=prec, recall=rec, f1=f1,
                    cm=cm, fi=fi, model_path=model_path,
                    cv_acc_mean=cv_acc_mean, cv_acc_std=cv_acc_std, cv_f1_mean=cv_f1_mean,
                )

                metric = {
                    "model": model_name, "horizon": horizon,
                    "n_train": len(X_train), "n_test": len(X_test),
                    "accuracy": acc, "precision_macro": prec,
                    "recall_macro": rec, "f1_macro": f1,
                    "confusion_matrix": cm,
                    "feature_importances": fi,
                    "cv_accuracy_mean": cv_acc_mean,
                    "cv_accuracy_std": cv_acc_std,
                    "cv_f1_mean": cv_f1_mean,
                    "insufficient": False,
                }
                results[f"{model_name}_{horizon}"] = metric
                logger.info("[ML] %s %s → acc=%.3f f1=%.3f cv_acc=%.3f±%.3f",
                           model_name, horizon, acc, f1,
                           cv_acc_mean or 0, cv_acc_std or 0)
                if on_progress:
                    on_progress(current_step, total_steps, f"{model_name}_{horizon}", f"Done {model_name} ({horizon}): Out-of-sample Acc={acc*100:.1f}%, Walk-Forward Acc={(cv_acc_mean or 0)*100:.1f}%")

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


def _store_metric(model_name, horizon, n_train, n_test, accuracy, precision,
                  recall, f1, cm, fi, model_path,
                  cv_acc_mean=None, cv_acc_std=None, cv_f1_mean=None):
    conn = get_connection()
    # Add CV columns to notes JSON for storage since schema is fixed
    notes_data = {}
    if cv_acc_mean is not None:
        notes_data["cv_accuracy_mean"] = cv_acc_mean
        notes_data["cv_accuracy_std"] = cv_acc_std
        notes_data["cv_f1_mean"] = cv_f1_mean
    conn.execute("""
        INSERT OR REPLACE INTO model_metric
        (model_name, horizon, trained_at, n_train, n_test,
         accuracy, precision_macro, recall_macro, f1_macro,
         confusion_matrix, feature_names, feature_importances,
         class_labels, is_sufficient, model_path, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)
    """, (
        model_name, horizon, datetime.now().isoformat(),
        n_train, n_test, accuracy, precision, recall, f1,
        json.dumps(cm), json.dumps(FEATURE_NAMES),
        json.dumps(fi) if fi else None,
        json.dumps(CLASS_LABELS), model_path,
        json.dumps(notes_data) if notes_data else None,
    ))
    conn.commit()
    conn.close()


def _store_insufficient(model_name, horizon, notes):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO model_metric
        (model_name, horizon, trained_at, is_sufficient, notes)
        VALUES (?,?,?,0,?)
    """, (model_name, horizon, datetime.now().isoformat(), notes))
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
        # Parse CV metrics from notes JSON
        if m.get("notes"):
            try:
                notes_data = json.loads(m["notes"])
                m["cv_accuracy_mean"] = notes_data.get("cv_accuracy_mean")
                m["cv_accuracy_std"]  = notes_data.get("cv_accuracy_std")
                m["cv_f1_mean"]       = notes_data.get("cv_f1_mean")
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
        "return_threshold_pct": RETURN_THRESHOLD,
        "compliance_disclaimer": "AI/model estimate — not investment advice.",
        "dataset_csv_available": os.path.exists(DATASET_CSV_PATH),
        "dataset_csv_rows": dataset_rows,
        "dataset_download_url": "/api/ml/dataset/download",
        "stock_price_rows": n_price_rows,
        "analysis_rows": n_analysis_rows,
    }


if __name__ == "__main__":
    print("Running ML training pipeline...")
    results = train_all()
    for k, v in results.items():
        if v.get("insufficient"):
            print(f"  {k}: INSUFFICIENT DATA — {v.get('message', '')}")
        elif v.get("error"):
            print(f"  {k}: ERROR — {v['error']}")
        else:
            print(f"  {k}: acc={v['accuracy']} prec={v['precision_macro']} rec={v['recall_macro']} f1={v['f1_macro']}")
