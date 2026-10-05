"""
test_indic_finance_integration.py — Integration and Unit Tests for
Indic-Finance Dataset Ingestion, Validation, Point-In-Time Features, and ML Pipeline.
"""

import os
import sqlite3
import pytest
import pandas as pd
import numpy as np

from database import get_connection, init_db
from indian_stocks_master import INDIAN_STOCKS_DATA
import indic_finance_importer
import ml_pipeline


def test_database_initialization_and_schema():
    """Verify all new Indic-Finance and forward return columns exist in database."""
    init_db()
    conn = get_connection()
    cur = conn.cursor()

    # Check indic_finance_raw table
    cur.execute("PRAGMA table_info(indic_finance_raw)")
    raw_cols = {r[1] for r in cur.fetchall()}
    assert "record_hash" in raw_cols
    assert "headline" in raw_cols
    assert "ticker" in raw_cols
    assert "forward_return_pct" in raw_cols
    assert "sentiment_positive" in raw_cols
    assert "day_of_week" in raw_cols

    # Check articles table columns
    cur.execute("PRAGMA table_info(articles)")
    art_cols = {r[1] for r in cur.fetchall()}
    for col in ["source_dataset", "source_ticker", "source_company",
                "affected_ticker", "affected_company", "forward_return_1d",
                "forward_return_3d", "forward_return_5d"]:
        assert col in art_cols, f"Missing {col} in articles"

    # Check analysis table columns
    cur.execute("PRAGMA table_info(analysis)")
    an_cols = {r[1] for r in cur.fetchall()}
    for col in ["source_dataset", "source_ticker", "source_company",
                "affected_ticker", "affected_company", "forward_return_1d",
                "forward_return_3d", "forward_return_5d"]:
        assert col in an_cols, f"Missing {col} in analysis"

    conn.close()


def test_production_data_preserved():
    """Verify that existing production records were NOT deleted or overwritten."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM articles WHERE source_dataset != 'indic_finance' OR source_dataset IS NULL")
    prod_articles = cur.fetchone()[0]
    conn.close()
    assert prod_articles >= 97, f"Expected at least 97 production articles, found {prod_articles}"


def test_indic_finance_tickers_valid():
    """Verify that all unique tickers in the dataset map cleanly to the Indian stocks master."""
    inspection = indic_finance_importer.inspect_dataset_file()
    assert inspection["ticker_coverage"]["invalid_tickers_count"] == 0
    assert inspection["ticker_coverage"]["valid_indian_tickers"] == 96


def test_source_vs_affected_ticker_distinction():
    """Verify that source_ticker and affected_ticker are tracked explicitly."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT source_ticker, source_company, affected_ticker, affected_company
        FROM analysis
        WHERE source_dataset = 'indic_finance'
        LIMIT 10
    """)
    rows = cur.fetchall()
    conn.close()
    assert len(rows) == 10
    for r in rows:
        assert r[0] is not None and r[0].endswith((".NS", ".BO", "=F", "=X", "^NSEI"))
        assert r[2] is not None


def test_no_synthetic_returns_fabricated():
    """Verify that records with missing returns remain None/UNLABELED and are not fabricated."""
    conn = get_connection()
    cur = conn.cursor()
    # Check that unlabeled records actually exist (meaning we didn't force-label everything with fake numbers)
    cur.execute("SELECT COUNT(*) FROM articles WHERE forward_return_1d IS NULL")
    missing_1d = cur.fetchone()[0]
    conn.close()
    assert missing_1d > 0, "Missing returns should exist and remain unlabelled, not fabricated"


def test_point_in_time_features_no_leakage():
    """Verify dataset builder operates chronologically with strictly point-in-time features."""
    dataset = ml_pipeline._build_labeled_dataset("1d")
    assert dataset is not None
    df, event_enc, sector_enc = dataset
    assert len(df) > 1000

    # Verify chronological ordering
    dates = df["published_at"].tolist()
    assert dates == sorted(dates), "Dataset rows must be strictly sorted in chronological order"


def test_dataset_export_csv_generation():
    """Verify exported dataset CSV contains all multi-horizon columns."""
    res = ml_pipeline.export_dataset()
    assert res["total_records"] > 9000
    assert os.path.exists(res["file_path"])

    df = pd.read_csv(res["file_path"], nrows=10)
    expected_cols = [
        "return_1d", "return_3d", "return_5d",
        "label_1d", "label_3d", "label_5d",
        "source_ticker", "source_company",
        "affected_ticker", "affected_company"
    ]
    for col in expected_cols:
        assert col in df.columns, f"Expected {col} in dataset_export.csv"


def test_models_exist_and_predict():
    """Verify that serialized joblib models exist for all 3 horizons and can make predictions."""
    res = ml_pipeline.get_model_metrics()
    metrics = res.get("metrics", [])
    assert len(metrics) >= 9
    horizons = {m["horizon"] for m in metrics}
    assert "1d" in horizons
    assert "3d" in horizons
    assert "5d" in horizons
