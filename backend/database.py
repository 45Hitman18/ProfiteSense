"""
database.py — Full schema for Market News AI
Tables: Company, Sector, NewsArticle (articles), NewsAnalysis (analysis),
        StockPrice, MarketEvent, Prediction, Watchlist, ModelMetric, market_cache,
        prediction_tracking (legacy accuracy tracker).
"""
import sqlite3
import json
import os
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "market_news.db")
_db_write_lock = threading.Lock()  # Serialize concurrent writes


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=60.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    cur = conn.cursor()

    # ── Sector ───────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sector (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL UNIQUE,
        description TEXT,
        created_at  TEXT DEFAULT (datetime('now'))
    )
    """)

    # ── Company ──────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS company (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        ticker      TEXT NOT NULL UNIQUE,
        sector_name TEXT,
        beta        REAL DEFAULT 1.0,
        market_cap  REAL,
        exchange    TEXT,
        created_at  TEXT DEFAULT (datetime('now'))
    )
    """)

    # ── NewsArticle (articles) ───────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS articles (
        id            TEXT PRIMARY KEY,
        title         TEXT NOT NULL,
        description   TEXT,
        summary       TEXT,
        url           TEXT,
        source        TEXT,
        published_at  TEXT,
        fetched_at    TEXT DEFAULT (datetime('now')),
        company       TEXT,
        ticker        TEXT,
        sector        TEXT,
        category      TEXT,
        sentiment     TEXT,
        sentiment_score REAL,
        impact_score  REAL,
        direction     TEXT,
        confidence    REAL,
        explanation   TEXT,
        raw_content   TEXT,
        created_at    TEXT DEFAULT (datetime('now'))
    )
    """)

    # ── NewsAnalysis ─────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS analysis (
        id                   TEXT PRIMARY KEY,
        article_id           TEXT NOT NULL,
        -- Entity fields
        ticker               TEXT,
        company_name         TEXT,
        sector               TEXT,
        beta                 REAL,
        all_entities         TEXT,
        -- Category & scope
        event_type           TEXT NOT NULL,
        event_display        TEXT,
        secondary_categories TEXT,
        scope                TEXT,
        affected_sectors     TEXT,
        -- Sentiment
        sentiment            TEXT NOT NULL,
        sentiment_score      REAL,
        sentiment_breakdown  TEXT,
        -- Impact & direction
        direction            TEXT NOT NULL,
        impact_level         TEXT NOT NULL,
        confidence           REAL,
        -- Outputs
        reason_explanation   TEXT,
        time_horizons        TEXT,
        historical_precedents TEXT,
        -- Compliance
        compliance_disclaimer TEXT,
        created_at           TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (article_id) REFERENCES articles(id)
    )
    """)

    # ── StockPrice (OHLCV per ticker per day) ────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS stock_price (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker      TEXT NOT NULL,
        date        TEXT NOT NULL,
        open        REAL,
        high        REAL,
        low         REAL,
        close       REAL,
        volume      REAL,
        adj_close   REAL,
        created_at  TEXT DEFAULT (datetime('now')),
        UNIQUE(ticker, date)
    )
    """)

    # ── MarketEvent (macro events / index snapshots) ─────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS market_event (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        event_date  TEXT NOT NULL,
        event_type  TEXT,
        description TEXT,
        nifty_close REAL,
        nifty_change_pct REAL,
        sp500_close REAL,
        sp500_change_pct REAL,
        vix         REAL,
        created_at  TEXT DEFAULT (datetime('now'))
    )
    """)

    # ── Prediction (ML model output per article & horizon) ───────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS prediction (
        id                  TEXT PRIMARY KEY,
        article_id          TEXT NOT NULL,
        model_name          TEXT NOT NULL,   -- LogisticRegression | RandomForest | GradientBoosting
        horizon             TEXT NOT NULL,   -- 1d | 3d | 5d
        predicted_class     TEXT NOT NULL,   -- Positive | Neutral | Negative
        prob_positive       REAL,
        prob_neutral        REAL,
        prob_negative       REAL,
        feature_vector      TEXT,            -- JSON
        actual_class        TEXT,            -- filled in after evaluation
        correct             INTEGER,         -- 1 | 0 | NULL
        evaluated_at        TEXT,
        created_at          TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (article_id) REFERENCES articles(id)
    )
    """)

    # ── ModelMetric (evaluation results per model & horizon) ─────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS model_metric (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        model_name      TEXT NOT NULL,
        horizon         TEXT NOT NULL,
        trained_at      TEXT NOT NULL,
        n_train         INTEGER,
        n_test          INTEGER,
        accuracy        REAL,
        precision_macro REAL,
        recall_macro    REAL,
        f1_macro        REAL,
        confusion_matrix TEXT,    -- JSON [[TP,FP,...],...]
        feature_names   TEXT,     -- JSON list
        feature_importances TEXT, -- JSON list (RF/GB only)
        class_labels    TEXT,     -- JSON list
        is_sufficient   INTEGER DEFAULT 1,   -- 0 = "insufficient data" flag
        model_path      TEXT,
        notes           TEXT,
        UNIQUE(model_name, horizon)
    )
    """)

    # ── Watchlist ─────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS watchlist (
        ticker       TEXT PRIMARY KEY,
        company_name TEXT,
        sector       TEXT,
        added_at     TEXT DEFAULT (datetime('now')),
        notes        TEXT
    )
    """)

    # ── Market cache (live quote cache) ──────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS market_cache (
        ticker     TEXT PRIMARY KEY,
        price      REAL,
        change_pct REAL,
        currency   TEXT,
        market_cap REAL,
        pe_ratio   REAL,
        high_52w   REAL,
        low_52w    REAL,
        volume     REAL,
        data_json  TEXT,
        updated_at TEXT DEFAULT (datetime('now'))
    )
    """)

    # ── Legacy prediction tracking (for backtest accuracy) ───────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS prediction_tracking (
        id                  TEXT PRIMARY KEY,
        article_id          TEXT,
        ticker              TEXT,
        prediction_date     TEXT,
        initial_price       REAL,
        predicted_direction TEXT,
        impact_level        TEXT,
        confidence          REAL,
        event_type          TEXT,
        scope               TEXT,
        actual_1d_change    REAL,
        actual_3d_change    REAL,
        actual_5d_change    REAL,
        outcome_1d          TEXT,
        outcome_3d          TEXT,
        outcome_5d          TEXT,
        status              TEXT DEFAULT 'PENDING',
        evaluated_at        TEXT,
        FOREIGN KEY (article_id) REFERENCES articles(id)
    )
    """)

    # ── Indic-Finance Raw Archive Table ───────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS indic_finance_raw (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        record_hash          TEXT UNIQUE,
        date                 TEXT,
        parsed_date          TEXT,
        headline             TEXT,
        ticker               TEXT,
        source               TEXT,
        url                  TEXT,
        sentiment_label      TEXT,
        sentiment_positive   REAL,
        sentiment_negative   REAL,
        sentiment_neutral    REAL,
        forward_return_pct   REAL,
        return_direction     INTEGER,
        snippet              TEXT,
        google_query         TEXT,
        username             TEXT,
        subreddit            TEXT,
        score                REAL,
        num_comments         REAL,
        flair                TEXT,
        headline_len         INTEGER,
        word_count           INTEGER,
        has_number           INTEGER,
        has_percent          INTEGER,
        day_of_week          TEXT,
        month                INTEGER,
        quarter              INTEGER,
        year                 INTEGER,
        is_weekend           INTEGER,
        imported_at          TEXT DEFAULT (datetime('now'))
    )
    """)

    # ── Safe column migrations for existing DBs ───────────────────
    _add_cols(cur, "analysis", [
        ("beta",                  "REAL"),
        ("all_entities",          "TEXT"),
        ("event_display",         "TEXT"),
        ("secondary_categories",  "TEXT"),
        ("scope",                 "TEXT"),
        ("affected_sectors",      "TEXT"),
        ("sentiment_breakdown",   "TEXT"),
        ("compliance_disclaimer", "TEXT"),
        ("source_dataset",        "TEXT"),
        ("source_ticker",         "TEXT"),
        ("source_company",        "TEXT"),
        ("affected_ticker",       "TEXT"),
        ("affected_company",      "TEXT"),
        ("forward_return_1d",     "REAL"),
        ("forward_return_3d",     "REAL"),
        ("forward_return_5d",     "REAL"),
    ])
    _add_cols(cur, "articles", [
        ("description",        "TEXT"),
        ("fetched_at",         "TEXT"),
        ("company",            "TEXT"),
        ("ticker",             "TEXT"),
        ("sector",             "TEXT"),
        ("category",           "TEXT"),
        ("sentiment",          "TEXT"),
        ("sentiment_score",    "REAL"),
        ("impact_score",       "REAL"),
        ("direction",          "TEXT"),
        ("confidence",         "REAL"),
        ("explanation",        "TEXT"),
        ("source_dataset",     "TEXT"),
        ("source_ticker",      "TEXT"),
        ("source_company",     "TEXT"),
        ("affected_ticker",    "TEXT"),
        ("affected_company",   "TEXT"),
        ("forward_return_1d",  "REAL"),
        ("forward_return_3d",  "REAL"),
        ("forward_return_5d",  "REAL"),
        ("sentiment_positive", "REAL"),
        ("sentiment_negative", "REAL"),
        ("sentiment_neutral",  "REAL"),
        ("return_direction",   "INTEGER"),
    ])
    _add_cols(cur, "prediction_tracking", [
        ("impact_level",  "TEXT"),
        ("confidence",    "REAL"),
        ("event_type",    "TEXT"),
        ("scope",         "TEXT"),
        ("outcome_1d",    "TEXT"),
        ("outcome_3d",    "TEXT"),
        ("outcome_5d",    "TEXT"),
    ])

    conn.commit()
    conn.close()


def _add_cols(cur: sqlite3.Cursor, table: str, cols: list) -> None:
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}
    for col_name, col_type in cols:
        if col_name not in existing:
            try:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass


def save_analysis(article_id: str, result: dict, conn: Optional[sqlite3.Connection] = None) -> str:
    import uuid
    analysis_id = str(uuid.uuid4())
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True
        
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO analysis (
            id, article_id,
            ticker, company_name, sector, beta, all_entities,
            event_type, event_display, secondary_categories, scope, affected_sectors,
            sentiment, sentiment_score, sentiment_breakdown,
            direction, impact_level, confidence,
            reason_explanation, time_horizons, historical_precedents,
            compliance_disclaimer
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        analysis_id, article_id,
        result.get("ticker"), result.get("company_name"), result.get("sector"),
        result.get("beta"), json.dumps(result.get("all_entities", [])),
        result.get("event_type"), result.get("event_display"),
        json.dumps(result.get("secondary_categories", [])),
        result.get("scope"), json.dumps(result.get("affected_sectors", [])),
        result.get("sentiment"), result.get("sentiment_score"),
        json.dumps(result.get("sentiment_breakdown", {})),
        result.get("direction"), result.get("impact_level"), result.get("confidence"),
        result.get("reason_explanation"),
        json.dumps(result.get("time_horizons", {})),
        json.dumps(result.get("historical_precedents", {})),
        result.get("compliance_disclaimer"),
    ))
    conn.commit()
    if close_after:
        conn.close()
    return analysis_id


if __name__ == "__main__":
    init_db()
    print("Database initialised at", DB_PATH)
