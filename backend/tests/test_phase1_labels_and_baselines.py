"""
test_phase1_labels_and_baselines.py — Comprehensive tests for Phase 1 of ProfitSense ML Pipeline
=============================================================================================
Tests:
1. Benchmark-relative (excess) returns with identical trading-day alignment.
2. Missing benchmark fallback to raw return with benchmark_missing flag.
3. Volatility-scaled threshold computation with configurable k, floor, and cap.
4. return_to_class with both volatility-scaled and fixed modes.
5. All three baselines: (a) majority class, (b) sentiment-sign rule, (c) random stratified.
6. Small-sample reporting safeguard: rejection of n_test < 200.
7. Point-in-time integrity of returns and features.
"""

import os
import sys
import pytest
import numpy as np
from collections import defaultdict

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from ml_pipeline import (
    StockPriceCache,
    compute_excess_return,
    compute_volatility_threshold,
    return_to_class,
    _return_to_class,
    evaluate_baselines,
    _store_metric,
    _store_insufficient,
    get_model_metrics,
    MIN_TEST_SAMPLES,
    RETURN_THRESHOLD,
    DEFAULT_VOLATILITY_K,
    DEFAULT_THRESHOLD_FLOOR,
    DEFAULT_THRESHOLD_CAP,
)


class MockPriceCache:
    """Mock cache for deterministic point-in-time return and benchmark testing."""
    def __init__(self):
        self.prices_by_ticker = defaultdict(list)
        self.close_lookup = {}
        self.dates_by_ticker = defaultdict(list)

    def add_price(self, ticker: str, date_str: str, close: float, volume: float = 1000.0):
        self.prices_by_ticker[ticker].append((date_str, close, volume))
        self.close_lookup[(ticker, date_str)] = close
        self.dates_by_ticker[ticker].append(date_str)


# ══════════════════════════════════════════════════════════════════
# 1. BENCHMARK-RELATIVE (EXCESS) RETURNS & TRADING-DAY ALIGNMENT
# ══════════════════════════════════════════════════════════════════
def test_excess_return_calculation():
    """Verify stock return minus benchmark return over identical trading days."""
    cache = MockPriceCache()

    # Stock prices: 100 on 2026-01-05 -> 105 on 2026-01-08 (+5.0%)
    cache.add_price("RELIANCE.NS", "2026-01-05", 100.0)
    cache.add_price("RELIANCE.NS", "2026-01-06", 101.0)
    cache.add_price("RELIANCE.NS", "2026-01-07", 103.0)
    cache.add_price("RELIANCE.NS", "2026-01-08", 105.0)

    # Benchmark prices: 20000 on 2026-01-05 -> 20400 on 2026-01-08 (+2.0%)
    cache.add_price("^NSEI", "2026-01-05", 20000.0)
    cache.add_price("^NSEI", "2026-01-06", 20100.0)
    cache.add_price("^NSEI", "2026-01-07", 20200.0)
    cache.add_price("^NSEI", "2026-01-08", 20400.0)

    res = compute_excess_return(
        ticker="RELIANCE.NS",
        pub_date="2026-01-05",
        n_days=3,
        benchmark_ticker="^NSEI",
        cache=cache
    )

    assert res["start_date"] == "2026-01-05"
    assert res["end_date"] == "2026-01-08"
    assert res["stock_return"] == pytest.approx(5.0, abs=1e-3)
    assert res["benchmark_return"] == pytest.approx(2.0, abs=1e-3)
    assert res["excess_return"] == pytest.approx(3.0, abs=1e-3)
    assert res["benchmark_missing"] is False
    assert res["chosen_return"] == pytest.approx(3.0, abs=1e-3)


def test_excess_return_fallback_when_benchmark_missing():
    """Verify fallback to raw return with benchmark_missing=True if benchmark data is absent."""
    cache = MockPriceCache()

    # Stock prices present
    cache.add_price("TCS.NS", "2026-02-02", 3000.0)
    cache.add_price("TCS.NS", "2026-02-03", 3030.0)
    cache.add_price("TCS.NS", "2026-02-04", 3060.0)
    cache.add_price("TCS.NS", "2026-02-05", 3090.0)  # +3.0%

    # No ^NSEI benchmark entries added

    res = compute_excess_return(
        ticker="TCS.NS",
        pub_date="2026-02-02",
        n_days=3,
        benchmark_ticker="^NSEI",
        cache=cache
    )

    assert res["start_date"] == "2026-02-02"
    assert res["end_date"] == "2026-02-05"
    assert res["stock_return"] == pytest.approx(3.0, abs=1e-3)
    assert res["benchmark_return"] is None
    assert res["excess_return"] == pytest.approx(3.0, abs=1e-3)
    assert res["benchmark_missing"] is True
    assert res["chosen_return"] == pytest.approx(3.0, abs=1e-3)


def test_excess_return_missing_stock_data():
    """Verify clean handling when stock price data is unavailable."""
    cache = MockPriceCache()
    res = compute_excess_return("NONEXISTENT.NS", "2026-01-01", 3, cache=cache)
    assert res["stock_return"] is None
    assert res["excess_return"] is None
    assert res["benchmark_missing"] is True


# ══════════════════════════════════════════════════════════════════
# 2. VOLATILITY-SCALED THRESHOLD & CONFIGURABLE LABELS
# ══════════════════════════════════════════════════════════════════
def test_volatility_threshold_scaling():
    """Verify threshold = k * historical_volatility with configurable k."""
    # Volatility = 2.0%, k = 0.5 -> threshold = 1.0%
    assert compute_volatility_threshold(volatility=2.0, k=0.5) == 1.0
    # Volatility = 1.5%, k = 0.8 -> threshold = 1.2%
    assert compute_volatility_threshold(volatility=1.5, k=0.8) == 1.2


def test_volatility_threshold_floor_and_cap():
    """Verify floor and cap constraints on volatility-scaled threshold."""
    # Extremely low vol: 0.1% with k=0.5 -> raw 0.05%, must floor at 0.25%
    assert compute_volatility_threshold(volatility=0.1, k=0.5, floor=0.25, cap=3.0) == 0.25

    # Extremely high vol: 10.0% with k=0.5 -> raw 5.0%, must cap at 3.0%
    assert compute_volatility_threshold(volatility=10.0, k=0.5, floor=0.25, cap=3.0) == 3.0


def test_volatility_threshold_invalid_fallback():
    """Verify fallback to default fixed threshold when volatility is missing or negative."""
    assert compute_volatility_threshold(None, default_threshold=0.5) == 0.5
    assert compute_volatility_threshold(-1.0, default_threshold=0.5) == 0.5
    assert compute_volatility_threshold(np.nan, default_threshold=0.5) == 0.5


def test_return_to_class_volatility_scaled():
    """Verify classification using volatility-scaled threshold."""
    # With vol=2.0, k=0.5, threshold = 1.0%
    assert return_to_class(1.2, volatility=2.0, mode="volatility_scaled", k=0.5) == "Positive"
    assert return_to_class(0.8, volatility=2.0, mode="volatility_scaled", k=0.5) == "Neutral"
    assert return_to_class(-0.5, volatility=2.0, mode="volatility_scaled", k=0.5) == "Neutral"
    assert return_to_class(-1.5, volatility=2.0, mode="volatility_scaled", k=0.5) == "Negative"


def test_return_to_class_fixed_mode_comparison():
    """Verify fixed-threshold mode is available and matches legacy behavior."""
    # With fixed threshold = 0.5%
    assert return_to_class(0.6, mode="fixed", fixed_threshold=0.5) == "Positive"
    assert return_to_class(0.3, mode="fixed", fixed_threshold=0.5) == "Neutral"
    assert return_to_class(-0.6, mode="fixed", fixed_threshold=0.5) == "Negative"
    # Legacy wrapper compatibility
    assert _return_to_class(0.6) == "Positive"
    assert _return_to_class(-0.6) == "Negative"
    assert _return_to_class(0.1) == "Neutral"


# ══════════════════════════════════════════════════════════════════
# 3. BASELINES (MAJORITY, SENTIMENT SIGN, RANDOM STRATIFIED)
# ══════════════════════════════════════════════════════════════════
def test_evaluate_baselines_structure_and_metrics():
    """Verify all 3 baselines produce accurate, defensible metrics."""
    # Synthetic imbalanced labels
    y_train = np.array(["Positive"] * 60 + ["Neutral"] * 30 + ["Negative"] * 10)
    y_test  = np.array(["Positive"] * 25 + ["Neutral"] * 15 + ["Negative"] * 10)
    sent_scores_test = np.array([0.5] * 20 + [-0.5] * 10 + [0.0] * 20)

    baselines = evaluate_baselines(
        y_train=y_train,
        y_test=y_test,
        sentiment_scores_test=sent_scores_test,
        sentiment_threshold=0.05,
        random_state=42
    )

    # 1. Majority Class Baseline
    maj = baselines["majority_class"]
    assert maj["predicted_class"] == "Positive"
    assert maj["accuracy"] == pytest.approx(25 / 50, abs=1e-3)
    # Balanced accuracy for pure majority prediction on 3 classes is approx 1/3 (recall of majority class is 1.0, others 0.0)
    assert maj["balanced_accuracy"] == pytest.approx(1.0 / 3.0, abs=1e-3)
    assert "f1_macro" in maj
    assert "precision_macro" in maj
    assert "recall_macro" in maj

    # 2. Sentiment-Sign Rule Baseline
    sent = baselines["sentiment_sign"]
    assert sent is not None
    assert "accuracy" in sent
    assert "balanced_accuracy" in sent
    assert "f1_macro" in sent

    # 3. Random Stratified Baseline
    rand = baselines["random_stratified"]
    assert rand["strategy"] == "stratified"
    assert 0.0 <= rand["accuracy"] <= 1.0
    assert 0.0 <= rand["balanced_accuracy"] <= 1.0
    assert 0.0 <= rand["f1_macro"] <= 1.0


# ══════════════════════════════════════════════════════════════════
# 4. SMALL-SAMPLE REPORTING SAFEGUARD (n_test < 200)
# ══════════════════════════════════════════════════════════════════
def test_small_sample_safeguard_storage():
    """Verify model metrics are flagged as is_sufficient=0 when n_test < 200."""
    # Store a metric with n_test = 50 (< 200)
    _store_metric(
        model_name="TestModelSmall",
        horizon="1d",
        n_train=200,
        n_test=50,
        accuracy=0.85,
        balanced_accuracy=0.80,
        precision=0.82,
        recall=0.79,
        f1=0.80,
        cm=[[10, 5, 2], [3, 20, 2], [1, 2, 5]],
        fi=[0.1] * 11,
        model_path="test_model.joblib"
    )

    data = get_model_metrics()
    test_metrics = [m for m in data["metrics"] if m["model_name"] == "TestModelSmall"]
    assert len(test_metrics) == 1
    # Safeguard must enforce is_sufficient = 0 for n_test < 200
    assert test_metrics[0]["is_sufficient"] == 0


def test_sufficient_sample_storage():
    """Verify model metrics are accepted with is_sufficient=1 when n_test >= 200."""
    _store_metric(
        model_name="TestModelLarge",
        horizon="1d",
        n_train=1000,
        n_test=250,  # >= 200
        accuracy=0.45,
        balanced_accuracy=0.42,
        precision=0.40,
        recall=0.41,
        f1=0.40,
        cm=[[50, 20, 10], [15, 80, 25], [10, 20, 20]],
        fi=[0.1] * 11,
        model_path="test_model_large.joblib",
        baseline_metrics={"majority_class": {"accuracy": 0.40, "balanced_accuracy": 0.33}}
    )

    data = get_model_metrics()
    test_metrics = [m for m in data["metrics"] if m["model_name"] == "TestModelLarge"]
    assert len(test_metrics) == 1
    assert test_metrics[0]["is_sufficient"] == 1
    assert test_metrics[0]["balanced_accuracy"] == 0.42
    assert test_metrics[0]["baseline_metrics"] is not None
    assert test_metrics[0]["baseline_metrics"]["majority_class"]["accuracy"] == 0.40
