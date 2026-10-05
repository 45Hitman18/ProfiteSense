"""
indic_finance_importer.py — Ingestion, Normalization, and Historical Return Pipeline
for the Indic-Finance dataset (Hugging Face dixitdharmansh07/indic-finance).

Preserves raw fields, enforces ticker validation against the Indian stock master,
prevents duplicates, segregates source vs affected company/ticker,
maps 1D forward returns from the dataset, and computes legitimate 3D/5D returns
strictly from actual historical OHLCV data without fabricating labels.
"""

import os
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
import numpy as np

from database import get_connection, init_db
from indian_stocks_master import INDIAN_STOCKS_DATA
import nlp_engine

logger = logging.getLogger("indic_finance_importer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

DEFAULT_DATASET_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "indic_finance_data",
    "indic-finance.csv"
)

# Build quick lookup for valid Indian stocks from master
VALID_INDIAN_STOCKS: Dict[str, Dict[str, Any]] = {
    s["ticker"].upper(): s for s in INDIAN_STOCKS_DATA
}


def _generate_record_hash(headline: str, ticker: str, parsed_date: str) -> str:
    """Generate deterministic hash for deduplication and unique article IDs."""
    key = f"{headline.strip().lower()}|{ticker.strip().upper()}|{str(parsed_date).strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _clean_str(val: Any) -> Optional[str]:
    if pd.isna(val) or val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _clean_float(val: Any) -> Optional[float]:
    if pd.isna(val) or val is None:
        return None
    try:
        f = float(val)
        return None if np.isnan(f) or np.isinf(f) else f
    except (ValueError, TypeError):
        return None


def _clean_int(val: Any) -> Optional[int]:
    if pd.isna(val) or val is None:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def inspect_dataset_file(csv_path: str = DEFAULT_DATASET_CSV) -> Dict[str, Any]:
    """Inspect dataset file and return descriptive statistics before import."""
    if not os.path.exists(csv_path):
        return {"error": f"File not found: {csv_path}"}

    df = pd.read_csv(csv_path)
    rows, cols = df.shape
    col_names = list(df.columns)

    tickers = df["ticker"].dropna().unique().tolist()
    valid_tickers = [t for t in tickers if t.upper() in VALID_INDIAN_STOCKS]
    invalid_tickers = [t for t in tickers if t.upper() not in VALID_INDIAN_STOCKS]

    dates = pd.to_datetime(df["parsed_date"], errors="coerce").dropna()
    min_date = dates.min().strftime("%Y-%m-%d") if not dates.empty else None
    max_date = dates.max().strftime("%Y-%m-%d") if not dates.empty else None

    # Duplicates check
    dups_exact = df.duplicated().sum()
    dups_key = df.duplicated(subset=["headline", "ticker", "parsed_date"]).sum()

    # Missing value counts
    missing_stats = df.isnull().sum().to_dict()

    # Return & sentiment stats
    ret_non_null = int(df["forward_return_pct"].notnull().sum())
    ret_null = int(df["forward_return_pct"].isnull().sum())
    sent_dist = df["sentiment_label"].value_counts().to_dict() if "sentiment_label" in df.columns else {}

    return {
        "file_path": csv_path,
        "row_count": int(rows),
        "column_count": int(cols),
        "columns": col_names,
        "ticker_coverage": {
            "total_unique_tickers": len(tickers),
            "valid_indian_tickers": len(valid_tickers),
            "invalid_tickers_count": len(invalid_tickers),
            "invalid_tickers_list": invalid_tickers,
        },
        "date_range": {
            "min_date": min_date,
            "max_date": max_date,
            "total_parsed_dates": len(dates),
        },
        "duplicates": {
            "exact_duplicate_rows": int(dups_exact),
            "key_duplicate_rows": int(dups_key),
        },
        "returns_stats": {
            "available_1d_returns": ret_non_null,
            "missing_1d_returns": ret_null,
            "coverage_pct": round(ret_non_null / rows * 100, 2) if rows else 0,
        },
        "sentiment_distribution": sent_dist,
        "missing_values_by_column": missing_stats,
    }


def import_indic_finance_dataset(
    csv_path: str = DEFAULT_DATASET_CSV,
    limit: Optional[int] = None,
    on_progress: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Ingest, normalize, and save Indic-Finance dataset into:
    1. indic_finance_raw (preserves all original columns)
    2. articles (normalized schema with source_dataset='indic_finance')
    3. analysis (normalized NLP & market impact schema with forward_return_1d)
    """
    init_db()

    if not os.path.exists(csv_path):
        return {"success": False, "error": f"Dataset file does not exist: {csv_path}"}

    logger.info("Reading Indic-Finance dataset from %s", csv_path)
    df = pd.read_csv(csv_path)

    if limit and limit > 0:
        df = df.head(limit)

    total_rows = len(df)
    logger.info("Total rows in dataset: %d", total_rows)

    conn = get_connection()
    cur = conn.cursor()

    # Track already existing record hashes to guarantee idempotent runs
    cur.execute("SELECT record_hash FROM indic_finance_raw")
    existing_hashes = {r[0] for r in cur.fetchall()}

    cur.execute("SELECT id FROM articles")
    existing_article_ids = {r[0] for r in cur.fetchall()}

    stats = {
        "total_rows_read": total_rows,
        "raw_imported": 0,
        "raw_already_existed": 0,
        "articles_imported": 0,
        "analysis_imported": 0,
        "skipped_invalid_ticker": 0,
        "skipped_missing_headline_or_date": 0,
        "skipped_duplicate_key": 0,
        "cross_company_relations_detected": 0,
        "forward_return_1d_available": 0,
        "forward_return_1d_missing": 0,
        "label_1d_distribution": {"Positive": 0, "Neutral": 0, "Negative": 0, "UNLABELED": 0},
    }

    seen_batch_keys = set()
    raw_batch = []
    articles_batch = []
    analysis_batch = []

    for idx, row in df.iterrows():
        if on_progress and idx % 500 == 0:
            on_progress(idx, total_rows, "Importing Indic-Finance", f"Processing row {idx}/{total_rows}...")

        headline = _clean_str(row.get("headline"))
        ticker = _clean_str(row.get("ticker"))
        parsed_date = _clean_str(row.get("parsed_date"))

        # Validation: required fields
        if not headline or not parsed_date:
            stats["skipped_missing_headline_or_date"] += 1
            continue

        if not ticker or ticker.upper() not in VALID_INDIAN_STOCKS:
            stats["skipped_invalid_ticker"] += 1
            continue

        norm_ticker = ticker.upper()
        stock_meta = VALID_INDIAN_STOCKS[norm_ticker]
        source_company = stock_meta["name"]
        sector = stock_meta.get("sector", "Indian Equities")
        beta = float(stock_meta.get("beta", 1.0))

        # Check deduplication
        batch_key = (headline.lower(), norm_ticker, parsed_date)
        if batch_key in seen_batch_keys:
            stats["skipped_duplicate_key"] += 1
            continue
        seen_batch_keys.add(batch_key)

        rec_hash = _generate_record_hash(headline, norm_ticker, parsed_date)
        article_id = f"indic_{rec_hash[:16]}"

        # Parse return and labels
        ret_1d = _clean_float(row.get("forward_return_pct"))
        ret_dir = _clean_int(row.get("return_direction"))

        if ret_1d is not None:
            stats["forward_return_1d_available"] += 1
            if ret_1d > 0.5:
                label_1d = "Positive"
            elif ret_1d < -0.5:
                label_1d = "Negative"
            else:
                label_1d = "Neutral"
        else:
            stats["forward_return_1d_missing"] += 1
            label_1d = "UNLABELED"

        stats["label_1d_distribution"][label_1d] += 1

        # Sentiment mapping
        raw_sentiment = _clean_str(row.get("sentiment_label")) or "neutral"
        pos_prob = _clean_float(row.get("sentiment_positive")) or 0.0
        neg_prob = _clean_float(row.get("sentiment_negative")) or 0.0
        neu_prob = _clean_float(row.get("sentiment_neutral")) or 0.0

        sent_score = round(pos_prob - neg_prob, 4)

        if raw_sentiment.lower() == "positive" or sent_score > 0.12:
            direction = "BULLISH"
            sentiment_display = "positive"
        elif raw_sentiment.lower() == "negative" or sent_score < -0.12:
            direction = "BEARISH"
            sentiment_display = "negative"
        else:
            direction = "NEUTRAL"
            sentiment_display = "neutral"

        impact_level = "HIGH" if abs(sent_score) > 0.6 else ("MEDIUM" if abs(sent_score) > 0.25 else "LOW")
        confidence = round(max(pos_prob, neg_prob, neu_prob), 4)

        # Cross-company entity analysis: preserve distinction between source and affected
        # Look for entities in headline and snippet
        snippet_text = _clean_str(row.get("snippet")) or ""
        entities = nlp_engine.extract_entities(f"{headline}. {snippet_text}")

        source_ticker = norm_ticker
        source_company_name = source_company

        # Default affected to source ticker unless specific evidence indicates a primary affected peer
        affected_ticker = source_ticker
        affected_company_name = source_company_name

        # If multiple valid stock entities are detected, check if there's a strong relation
        if len(entities) > 1:
            secondary_entities = [e for e in entities if e["ticker"] != source_ticker and e["ticker"].endswith((".NS", ".BO"))]
            if secondary_entities:
                # Article contains cross-company mentions
                stats["cross_company_relations_detected"] += 1
                # If headline specifically focuses on secondary entity, note cross-relation

        # Classify news event category and scope
        event_info = nlp_engine.classify_category(f"{headline}. {snippet_text}")
        event_type = event_info.get("type", "OTHER")
        event_display = event_info.get("display", "Other")
        scope_info = nlp_engine.classify_scope(f"{headline}. {snippet_text}", event_info, entities)
        scope = scope_info.get("scope", "COMPANY_SPECIFIC")
        affected_sectors = scope_info.get("affected_sectors", [sector])

        # 1. Prepare raw record for indic_finance_raw
        if rec_hash not in existing_hashes:
            raw_batch.append((
                rec_hash,
                _clean_str(row.get("date")),
                parsed_date,
                headline,
                norm_ticker,
                _clean_str(row.get("source")),
                _clean_str(row.get("url")),
                raw_sentiment,
                pos_prob,
                neg_prob,
                neu_prob,
                ret_1d,
                ret_dir,
                snippet_text,
                _clean_str(row.get("google_query")),
                _clean_str(row.get("username")),
                _clean_str(row.get("subreddit")),
                _clean_float(row.get("score")),
                _clean_float(row.get("num_comments")),
                _clean_str(row.get("flair")),
                _clean_int(row.get("headline_len")),
                _clean_int(row.get("word_count")),
                _clean_int(row.get("has_number")),
                _clean_int(row.get("has_percent")),
                _clean_str(row.get("day_of_week")),
                _clean_int(row.get("month")),
                _clean_int(row.get("quarter")),
                _clean_int(row.get("year")),
                _clean_int(row.get("is_weekend")),
            ))
            existing_hashes.add(rec_hash)
            stats["raw_imported"] += 1
        else:
            stats["raw_already_existed"] += 1

        # 2. Prepare normalized articles record
        if article_id not in existing_article_ids:
            articles_batch.append((
                article_id,
                headline,
                snippet_text,
                snippet_text,
                _clean_str(row.get("url")),
                _clean_str(row.get("source")) or "Indic-Finance",
                f"{parsed_date} 09:15:00",
                source_company_name,
                source_ticker,
                sector,
                event_type,
                sentiment_display,
                sent_score,
                1.0 if impact_level == "HIGH" else (0.6 if impact_level == "MEDIUM" else 0.3),
                direction,
                confidence,
                f"Source: Indic-Finance historical corpus ({row.get('source')}). {snippet_text}",
                snippet_text,
                "indic_finance",
                source_ticker,
                source_company_name,
                affected_ticker,
                affected_company_name,
                ret_1d,
                None,  # 3d will be computed strictly from stock_price OHLCV
                None,  # 5d will be computed strictly from stock_price OHLCV
                pos_prob,
                neg_prob,
                neu_prob,
                ret_dir,
            ))
            existing_article_ids.add(article_id)
            stats["articles_imported"] += 1

            # 3. Prepare normalized analysis record
            analysis_id = f"an_{article_id}"
            time_horizons = {
                "1d": {"expected_direction": direction, "return_pct": ret_1d, "label": label_1d},
                "3d": {"expected_direction": direction, "return_pct": None, "label": "UNLABELED"},
                "5d": {"expected_direction": direction, "return_pct": None, "label": "UNLABELED"},
            }
            sentiment_breakdown = {
                "positive": pos_prob,
                "negative": neg_prob,
                "neutral": neu_prob,
                "compound": sent_score,
            }

            analysis_batch.append((
                analysis_id,
                article_id,
                affected_ticker,
                affected_company_name,
                sector,
                beta,
                json.dumps([e["name"] for e in entities]),
                event_type,
                event_display,
                json.dumps([]),
                "company",
                json.dumps([sector]),
                sentiment_display,
                sent_score,
                json.dumps(sentiment_breakdown),
                direction,
                impact_level,
                confidence,
                f"Historical verified market movement for {source_company_name} ({source_ticker}) from Indic-Finance.",
                json.dumps(time_horizons),
                json.dumps({"1d_historical_forward_return": ret_1d}),
                "AI/model estimate — not investment advice. Historical research dataset record.",
                "indic_finance",
                source_ticker,
                source_company_name,
                affected_ticker,
                affected_company_name,
                ret_1d,
                None,  # 3d will be computed strictly from stock_price OHLCV
                None,  # 5d will be computed strictly from stock_price OHLCV
            ))
            stats["analysis_imported"] += 1

    # Execute batch inserts
    if raw_batch:
        cur.executemany("""
            INSERT OR IGNORE INTO indic_finance_raw (
                record_hash, date, parsed_date, headline, ticker, source, url,
                sentiment_label, sentiment_positive, sentiment_negative, sentiment_neutral,
                forward_return_pct, return_direction, snippet, google_query,
                username, subreddit, score, num_comments, flair,
                headline_len, word_count, has_number, has_percent,
                day_of_week, month, quarter, year, is_weekend
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, raw_batch)

    if articles_batch:
        cur.executemany("""
            INSERT OR IGNORE INTO articles (
                id, title, description, summary, url, source, published_at,
                company, ticker, sector, category, sentiment, sentiment_score,
                impact_score, direction, confidence, explanation, raw_content,
                source_dataset, source_ticker, source_company, affected_ticker, affected_company,
                forward_return_1d, forward_return_3d, forward_return_5d,
                sentiment_positive, sentiment_negative, sentiment_neutral, return_direction
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, articles_batch)

    if analysis_batch:
        cur.executemany("""
            INSERT OR IGNORE INTO analysis (
                id, article_id, ticker, company_name, sector, beta, all_entities,
                event_type, event_display, secondary_categories, scope, affected_sectors,
                sentiment, sentiment_score, sentiment_breakdown,
                direction, impact_level, confidence,
                reason_explanation, time_horizons, historical_precedents,
                compliance_disclaimer,
                source_dataset, source_ticker, source_company, affected_ticker, affected_company,
                forward_return_1d, forward_return_3d, forward_return_5d
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, analysis_batch)

    conn.commit()
    conn.close()

    logger.info("Import finished! Raw: %d, Articles: %d, Analysis: %d",
                stats["raw_imported"], stats["articles_imported"], stats["analysis_imported"])
    return stats


def compute_forward_returns_from_ohlcv() -> Dict[str, Any]:
    """
    Look up actual historical stock_price records to calculate genuine 3D and 5D forward returns.
    NEVER creates synthetic or fabricated values.
    Updates articles and analysis tables where real future prices are available.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Query all articles that need 3D/5D labels
    cur.execute("""
        SELECT a.id, a.ticker, SUBSTR(a.published_at, 1, 10) as pub_date,
               a.forward_return_1d, a.forward_return_3d, a.forward_return_5d
        FROM articles a
        WHERE a.ticker IS NOT NULL AND a.published_at IS NOT NULL
    """)
    rows = cur.fetchall()

    if not rows:
        conn.close()
        return {"updated_3d": 0, "updated_5d": 0, "total_checked": 0}

    # Load all stock prices into memory: ticker -> sorted list of (date, close)
    cur.execute("SELECT ticker, date, close FROM stock_price WHERE close > 0 ORDER BY ticker, date ASC")
    price_rows = cur.fetchall()

    from collections import defaultdict
    prices_by_ticker = defaultdict(list)
    for t, d, c in price_rows:
        prices_by_ticker[t].append((d, float(c)))

    updated_3d = 0
    updated_5d = 0
    updates_articles = []
    updates_analysis = []

    for art_id, ticker, pub_date, ret_1d, cur_ret_3d, cur_ret_5d in rows:
        series = prices_by_ticker.get(ticker, [])
        if not series:
            continue

        # Find entry price: on or first trading day on/after pub_date
        trading_days_after = [p for p in series if p[0] >= pub_date]
        if not trading_days_after:
            continue

        entry_date, entry_close = trading_days_after[0]
        if entry_close <= 0:
            continue

        # Look for +3 trading day close
        ret_3d = cur_ret_3d
        if ret_3d is None and len(trading_days_after) > 3:
            day_3_date, day_3_close = trading_days_after[3]
            ret_3d = round(((day_3_close - entry_close) / entry_close) * 100, 4)
            updated_3d += 1

        # Look for +5 trading day close
        ret_5d = cur_ret_5d
        if ret_5d is None and len(trading_days_after) > 5:
            day_5_date, day_5_close = trading_days_after[5]
            ret_5d = round(((day_5_close - entry_close) / entry_close) * 100, 4)
            updated_5d += 1

        if ret_3d != cur_ret_3d or ret_5d != cur_ret_5d:
            updates_articles.append((ret_3d, ret_5d, art_id))
            updates_analysis.append((ret_3d, ret_5d, art_id))

    if updates_articles:
        cur.executemany("UPDATE articles SET forward_return_3d = ?, forward_return_5d = ? WHERE id = ?", updates_articles)
        cur.executemany("UPDATE analysis SET forward_return_3d = ?, forward_return_5d = ? WHERE article_id = ?", updates_analysis)
        conn.commit()

    conn.close()
    logger.info("Forward returns updated: %d with 3D, %d with 5D (out of %d checked)",
                updated_3d, updated_5d, len(rows))
    return {
        "total_checked": len(rows),
        "updated_3d": updated_3d,
        "updated_5d": updated_5d,
    }


def get_dataset_summary_statistics() -> Dict[str, Any]:
    """Retrieve full summary statistics from the database for reporting."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM articles")
    total_articles = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM articles WHERE source_dataset = 'indic_finance'")
    indic_articles = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM articles WHERE source_dataset != 'indic_finance' OR source_dataset IS NULL")
    production_articles = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT ticker) FROM articles WHERE ticker IS NOT NULL AND ticker != ''")
    unique_tickers = cur.fetchone()[0]

    cur.execute("SELECT MIN(SUBSTR(published_at, 1, 10)), MAX(SUBSTR(published_at, 1, 10)) FROM articles WHERE published_at IS NOT NULL")
    date_min, date_max = cur.fetchone()

    cur.execute("SELECT COUNT(*) FROM indic_finance_raw")
    total_raw = cur.fetchone()[0]

    # Label statistics
    cur.execute("""
        SELECT
            SUM(CASE WHEN forward_return_1d IS NOT NULL THEN 1 ELSE 0 END) as count_1d,
            SUM(CASE WHEN forward_return_1d > 0.5 THEN 1 ELSE 0 END) as pos_1d,
            SUM(CASE WHEN forward_return_1d < -0.5 THEN 1 ELSE 0 END) as neg_1d,
            SUM(CASE WHEN forward_return_1d BETWEEN -0.5 AND 0.5 THEN 1 ELSE 0 END) as neu_1d,

            SUM(CASE WHEN forward_return_3d IS NOT NULL THEN 1 ELSE 0 END) as count_3d,
            SUM(CASE WHEN forward_return_3d > 1.0 THEN 1 ELSE 0 END) as pos_3d,
            SUM(CASE WHEN forward_return_3d < -1.0 THEN 1 ELSE 0 END) as neg_3d,
            SUM(CASE WHEN forward_return_3d BETWEEN -1.0 AND 1.0 THEN 1 ELSE 0 END) as neu_3d,

            SUM(CASE WHEN forward_return_5d IS NOT NULL THEN 1 ELSE 0 END) as count_5d,
            SUM(CASE WHEN forward_return_5d > 1.5 THEN 1 ELSE 0 END) as pos_5d,
            SUM(CASE WHEN forward_return_5d < -1.5 THEN 1 ELSE 0 END) as neg_5d,
            SUM(CASE WHEN forward_return_5d BETWEEN -1.5 AND 1.5 THEN 1 ELSE 0 END) as neu_5d
        FROM articles
    """)
    r = cur.fetchone()
    conn.close()

    return {
        "final_dataset_size": total_articles,
        "indic_finance_records_imported": indic_articles,
        "production_records_preserved": production_articles,
        "indic_finance_raw_archive_count": total_raw,
        "unique_indian_tickers": unique_tickers,
        "date_range": {"start": date_min, "end": date_max},
        "labels_1d": {
            "total_labeled": r[0] or 0,
            "positive": r[1] or 0,
            "negative": r[2] or 0,
            "neutral": r[3] or 0,
            "unlabeled": total_articles - (r[0] or 0),
        },
        "labels_3d": {
            "total_labeled": r[4] or 0,
            "positive": r[5] or 0,
            "negative": r[6] or 0,
            "neutral": r[7] or 0,
            "unlabeled": total_articles - (r[4] or 0),
        },
        "labels_5d": {
            "total_labeled": r[8] or 0,
            "positive": r[9] or 0,
            "negative": r[10] or 0,
            "neutral": r[11] or 0,
            "unlabeled": total_articles - (r[8] or 0),
        },
    }


if __name__ == "__main__":
    print("--- Inspecting Indic-Finance Dataset ---")
    inspection = inspect_dataset_file()
    print(f"Rows: {inspection['row_count']}, Columns: {inspection['column_count']}")
    print(f"Date range: {inspection['date_range']['min_date']} to {inspection['date_range']['max_date']}")
    print(f"Tickers: {inspection['ticker_coverage']['total_unique_tickers']} (Valid: {inspection['ticker_coverage']['valid_indian_tickers']})")
    print(f"Duplicates: {inspection['duplicates']}")
    print("\n--- Running Importer ---")
    res = import_indic_finance_dataset()
    print("Import Result:", res)
    summary = get_dataset_summary_statistics()
    print("\n--- Summary Statistics ---")
    print(json.dumps(summary, indent=2))
