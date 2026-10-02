import json
import asyncio
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import init_db, get_connection, save_analysis
from nlp_engine import analyze_article, _time_horizons, MANDATORY_DISCLAIMER
from news_collector import sync_all_news
from providers.market.aggregator import MarketAggregator
from backtest_tracker import get_accuracy_metrics
from ml_pipeline import train_all, get_model_metrics, predict_article, export_dataset, DATASET_CSV_PATH
from stock_collector import fetch_and_store_prices
from indian_stocks_master import stock_master_index
from trade_engine import compute_trade_analysis
from price_brackets import get_stock_price_info, classify_price_bracket, BRACKET_CONFIG

app = FastAPI(
    title="Market News AI API",
    description="Full-stack AI platform for real-time stock market news analysis, sentiment scoring, and time-horizon impact estimation.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

market_aggregator = MarketAggregator()

class CustomAnalysisRequest(BaseModel):
    title: str
    content: Optional[str] = ""
    ticker_hint: Optional[str] = None

class WatchlistRequest(BaseModel):
    ticker: str
    notes: Optional[str] = ""

async def _periodic_news_sync():
    """Background task running every 20 minutes, respecting free-tier rate limits."""
    await asyncio.sleep(15)  # Initial grace period
    while True:
        try:
            sync_all_news()
        except Exception as e:
            print(f"Background scheduler sync note: {e}")
        await asyncio.sleep(1200)  # 20 minutes

@app.on_event("startup")
async def startup_event():
    init_db()
    asyncio.create_task(_periodic_news_sync())

@app.get("/")
def root():
    return {
        "status": "online",
        "message": "Market News AI Backend API is running.",
        "frontend_ui": "http://localhost:5173",
        "swagger_docs": "http://127.0.0.1:8000/docs",
        "api_health": "http://127.0.0.1:8000/api/health",
        "compliance_disclaimer": MANDATORY_DISCLAIMER
    }

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "Market News AI Backend API",
        "frontend_ui": "http://localhost:5173",
        "swagger_docs": "http://127.0.0.1:8000/docs",
        "api_health": "http://127.0.0.1:8000/api/health",
        "compliance_disclaimer": MANDATORY_DISCLAIMER
    }

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Market News AI",
        "compliance_disclaimer": MANDATORY_DISCLAIMER,
        "timestamp": datetime.now().isoformat(),
        "zero_paid_services_guarantee": True,
        "background_scheduler": "Running (20m cadence)"
    }

@app.get("/api/settings")
def get_settings():
    conn = get_connection()
    n_articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    n_prices   = conn.execute("SELECT COUNT(*) FROM stock_price").fetchone()[0]
    n_quotes   = conn.execute("SELECT COUNT(*) FROM market_cache").fetchone()[0]
    conn.close()
    return {
        "status": "healthy",
        "service": "Market News AI",
        "zero_paid_services_guarantee": True,
        "scheduler": {
            "cadence": "Every 20 minutes",
            "type": "Native AsyncIO Background Task",
            "status": "Active"
        },
        "cache": {
            "articles": n_articles,
            "prices": n_prices,
            "quotes": n_quotes
        },
        "compliance_disclaimer": MANDATORY_DISCLAIMER
    }

@app.get("/api/news")
def get_news(
    query: Optional[str] = None,
    ticker: Optional[str] = None,
    sector: Optional[str] = None,
    sentiment: Optional[str] = None,
    impact_level: Optional[str] = None,
    direction: Optional[str] = None,
    price_bracket: Optional[str] = "ALL",
    sort_by: Optional[str] = "priority",
    sync: Optional[bool] = False,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    if sync:
        try:
            sync_all_news()
        except Exception as e:
            print(f"Sync on fetch error: {e}")

    offset = (page - 1) * limit
    conn = get_connection()
    cursor = conn.cursor()
    
    where_clauses = []
    params = []
    
    if query:
        where_clauses.append("(a.title LIKE ? OR a.summary LIKE ? OR an.company_name LIKE ?)")
        wildcard = f"%{query}%"
        params.extend([wildcard, wildcard, wildcard])
        
    if ticker:
        where_clauses.append("an.ticker = ?")
        params.append(ticker.upper())
        
    if sector:
        where_clauses.append("an.sector = ?")
        params.append(sector)
        
    if sentiment:
        where_clauses.append("an.sentiment = ?")
        params.append(sentiment.capitalize())
        
    if impact_level:
        where_clauses.append("an.impact_level = ?")
        params.append(impact_level.upper())
        
    if direction:
        where_clauses.append("an.direction = ?")
        params.append(direction.upper())
        
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    
    if sort_by == "latest":
        order_clause = "ORDER BY a.published_at DESC"
    elif sort_by == "impact":
        order_clause = """
        ORDER BY 
            CASE an.impact_level
                WHEN 'HIGH' THEN 1
                WHEN 'MEDIUM' THEN 2
                WHEN 'LOW' THEN 3
                ELSE 4
            END ASC,
            ABS(an.sentiment_score) DESC,
            a.published_at DESC
        """
    elif sort_by == "confidence":
        order_clause = "ORDER BY an.confidence DESC, a.published_at DESC"
    else:  # "priority" (default): Recent days first, with HIGH impact catalysts taking top priority
        order_clause = """
        ORDER BY 
            DATE(a.published_at) DESC,
            CASE an.impact_level
                WHEN 'HIGH' THEN 1
                WHEN 'MEDIUM' THEN 2
                WHEN 'LOW' THEN 3
                ELSE 4
            END ASC,
            ABS(an.sentiment_score) DESC,
            an.confidence DESC,
            a.published_at DESC
        """

    select_sql = f"""
    SELECT
        a.id, a.title, a.summary, a.source, a.url, a.published_at, a.category,
        an.sentiment, an.sentiment_score, an.direction, an.impact_level,
        an.confidence, an.ticker, an.company_name, an.sector,
        an.event_type, an.event_display, an.secondary_categories,
        an.scope, an.affected_sectors, an.all_entities,
        an.sentiment_breakdown,
        an.reason_explanation, an.time_horizons, an.historical_precedents,
        an.created_at
    FROM articles a
    JOIN analysis an ON a.id = an.article_id
    {where_sql}
    {order_clause}
    """

    cursor.execute(select_sql, params)
    all_rows = cursor.fetchall()
    conn.close()

    def _j(v):
        try:
            return json.loads(v) if v else {}
        except Exception:
            return {}

    # Filter by price_bracket if specified
    filtered_rows = []
    for r in all_rows:
        t = r["ticker"]
        pinfo = get_stock_price_info(t)
        if price_bracket and price_bracket != "ALL":
            if pinfo["bracket_id"] != price_bracket:
                continue
        filtered_rows.append((r, pinfo))

    total_count = len(filtered_rows)
    sliced = filtered_rows[offset:offset + limit]

    items = []
    for r, pinfo in sliced:
        items.append({
            "id": r["id"],
            "title": r["title"],
            "summary": r["summary"],
            "source": r["source"],
            "url": r["url"],
            "published_at": r["published_at"],
            "category": r["category"],
            "stock_price": pinfo["price"],
            "price_bracket": pinfo["bracket_id"],
            "price_bracket_label": pinfo["bracket_label"],
            "price_bracket_color": pinfo["bracket_color"],
            "price_bracket_bg": pinfo["bracket_bg"],
            "price_bracket_border": pinfo["bracket_border"],
            "compliance_disclaimer": MANDATORY_DISCLAIMER,
            "analysis": {
                "sentiment":             r["sentiment"],
                "sentiment_score":       r["sentiment_score"],
                "sentiment_breakdown":   _j(r["sentiment_breakdown"]),
                "direction":             r["direction"],
                "impact_level":          r["impact_level"],
                "confidence":            r["confidence"],
                "ticker":                r["ticker"],
                "company_name":          r["company_name"],
                "sector":                r["sector"],
                "stock_price":           pinfo["price"],
                "price_bracket":         pinfo["bracket_id"],
                "price_bracket_label":   pinfo["bracket_label"],
                "price_bracket_color":   pinfo["bracket_color"],
                "price_bracket_bg":      pinfo["bracket_bg"],
                "price_bracket_border":  pinfo["bracket_border"],
                "all_entities":          _j(r["all_entities"]),
                "event_type":            r["event_type"],
                "event_display":         r["event_display"],
                "secondary_categories":  _j(r["secondary_categories"]),
                "scope":                 r["scope"],
                "affected_sectors":      _j(r["affected_sectors"]),
                "reason_explanation":    r["reason_explanation"],
                "time_horizons":         _j(r["time_horizons"]),
                "historical_precedents": _j(r["historical_precedents"]),
                "compliance_disclaimer": MANDATORY_DISCLAIMER,
            }
        })

    return {
        "page": page,
        "limit": limit,
        "total": total_count,
        "total_pages": (total_count + limit - 1) // limit if total_count > 0 else 1,
        "price_bracket": price_bracket,
        "compliance_disclaimer": MANDATORY_DISCLAIMER,
        "items": items
    }

@app.get("/api/news/categories")
def get_categories():
    """Return the full 28-category taxonomy with metadata."""
    from nlp_engine import NEWS_CATEGORIES
    return {
        "categories": [
            {"type": c["type"], "display": c["display"],
             "base_impact": c["base_impact"], "scope": c["scope"]}
            for c in NEWS_CATEGORIES
        ],
        "compliance_disclaimer": MANDATORY_DISCLAIMER,
    }


@app.get("/api/news/{article_id}")
def get_news_detail(article_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT
        a.id, a.title, a.summary, a.source, a.url, a.published_at, a.category, a.raw_content,
        an.sentiment, an.sentiment_score, an.direction, an.impact_level,
        an.confidence, an.ticker, an.company_name, an.sector,
        an.event_type, an.event_display, an.secondary_categories,
        an.scope, an.affected_sectors, an.all_entities,
        an.sentiment_breakdown,
        an.reason_explanation, an.time_horizons, an.historical_precedents,
        an.created_at
    FROM articles a
    JOIN analysis an ON a.id = an.article_id
    WHERE a.id = ?
    """, (article_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Article not found")

    def _j(v):
        try:
            return json.loads(v) if v else {}
        except Exception:
            return {}

    ticker = row["ticker"]
    quote = market_aggregator.get_quote(ticker) if ticker else None

    # Retrieve stored time_horizons or dynamically re-calibrate with live quote
    time_horizons = _j(row["time_horizons"])
    if quote and quote.get("price") and quote["price"] > 0:
        time_horizons = _time_horizons(
            direction=row["direction"] or "NEUTRAL",
            impact_level=row["impact_level"] or "MEDIUM",
            beta=quote.get("beta") or 1.0,
            confidence=float(row["confidence"] or 70.0),
            current_price=float(quote["price"]),
            sentiment_score=float(row["sentiment_score"] or 0.5),
            event_type=row["event_type"] or ""
        )

    return {
        "id":          row["id"],
        "title":       row["title"],
        "summary":     row["summary"],
        "source":      row["source"],
        "url":         row["url"],
        "published_at":row["published_at"],
        "category":    row["category"],
        "raw_content": row["raw_content"],
        "compliance_disclaimer": MANDATORY_DISCLAIMER,
        "analysis": {
            "sentiment":             row["sentiment"],
            "sentiment_score":       row["sentiment_score"],
            "sentiment_breakdown":   _j(row["sentiment_breakdown"]),
            "direction":             row["direction"],
            "impact_level":          row["impact_level"],
            "confidence":            row["confidence"],
            "ticker":                row["ticker"],
            "company_name":          row["company_name"],
            "sector":                row["sector"],
            "all_entities":          _j(row["all_entities"]),
            "event_type":            row["event_type"],
            "event_display":         row["event_display"],
            "secondary_categories":  _j(row["secondary_categories"]),
            "scope":                 row["scope"],
            "affected_sectors":      _j(row["affected_sectors"]),
            "reason_explanation":    row["reason_explanation"],
            "time_horizons":         time_horizons,
            "historical_precedents": _j(row["historical_precedents"]),
            "compliance_disclaimer": MANDATORY_DISCLAIMER,
        },
        "market_context": quote,
    }

@app.post("/api/news/sync")
async def trigger_news_sync(background_tasks: BackgroundTasks):
    result = await asyncio.to_thread(sync_all_news)
    return result

@app.post("/api/news/analyze-custom")
def analyze_custom_news(payload: CustomAnalysisRequest):
    if not payload.title or len(payload.title.strip()) < 5:
        raise HTTPException(status_code=400, detail="Headline must contain at least 5 characters.")
        
    analysis = analyze_article(payload.title, payload.content or "")
    if payload.ticker_hint:
        analysis["ticker"] = payload.ticker_hint.upper()
        
    quote = market_aggregator.get_quote(analysis["ticker"])
    if quote and quote.get("price") and quote["price"] > 0:
        analysis["time_horizons"] = _time_horizons(
            direction=analysis["direction"],
            impact_level=analysis["impact_level"],
            beta=quote.get("beta") or 1.0,
            confidence=float(analysis["confidence"]),
            current_price=float(quote["price"]),
            sentiment_score=float(analysis.get("sentiment_score") or 0.5),
            event_type=analysis.get("event_type") or ""
        )
    
    return {
        "title": payload.title,
        "content": payload.content,
        "analysis": analysis,
        "market_context": quote,
        "compliance_disclaimer": MANDATORY_DISCLAIMER,
        "analyzed_at": datetime.now().isoformat()
    }

@app.get("/api/tickers/{ticker}")
def get_ticker_details(ticker: str):
    clean_ticker = ticker.strip().upper()
    quote = market_aggregator.get_quote(clean_ticker)
    chart = market_aggregator.get_historical_chart(clean_ticker, period="1mo")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT a.id, a.title, a.source, a.published_at, an.sentiment, an.direction, an.impact_level, an.confidence
    FROM articles a
    JOIN analysis an ON a.id = an.article_id
    WHERE an.ticker = ?
    ORDER BY 
        DATE(a.published_at) DESC,
        CASE an.impact_level WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 WHEN 'LOW' THEN 3 ELSE 4 END ASC,
        an.confidence DESC,
        a.published_at DESC
    LIMIT 15
    """, (clean_ticker,))
    news_rows = cursor.fetchall()
    conn.close()
    
    related_news = [dict(r) for r in news_rows]
    
    if related_news:
        up_count = sum(1 for n in related_news if n["direction"] == "UP")
        down_count = sum(1 for n in related_news if n["direction"] == "DOWN")
        total = len(related_news)
        bullish_pct = round((up_count / total) * 100, 1)
        bearish_pct = round((down_count / total) * 100, 1)
    else:
        bullish_pct = 50.0
        bearish_pct = 50.0
        
    return {
        "quote": quote,
        "chart": chart,
        "related_news": related_news,
        "compliance_disclaimer": MANDATORY_DISCLAIMER,
        "sentiment_summary": {
            "bullish_pct": bullish_pct,
            "bearish_pct": bearish_pct,
            "neutral_pct": round(100.0 - bullish_pct - bearish_pct, 1),
            "signal": "BULLISH" if bullish_pct > 55 else ("BEARISH" if bearish_pct > 55 else "NEUTRAL")
        }
    }

@app.get("/api/market/overview")
def get_market_summary():
    overview = market_aggregator.get_market_overview()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT an.ticker, an.company_name, an.sentiment, COUNT(*) as cnt
        FROM analysis an
        WHERE an.ticker NOT GLOB '[0-9]*' AND LENGTH(an.ticker) >= 2 AND an.ticker NOT IN ('SPY', 'NVDA', 'AAPL', 'MSFT', 'TSLA', 'AMZN')
        GROUP BY an.ticker, an.company_name
        ORDER BY cnt DESC
        LIMIT 6
    """)
    rows = cursor.fetchall()
    top_tickers = []
    for r in rows:
        top_tickers.append({
            "ticker": r["ticker"].replace(".NS", ""),
            "company": r["company_name"],
            "sentiment": r["sentiment"],
            "count": r["cnt"]
        })
    overview["top_tickers"] = top_tickers
    
    cursor.execute("SELECT sentiment, COUNT(*) FROM analysis GROUP BY sentiment")
    dist = {"positive": 0, "neutral": 0, "negative": 0}
    for row in cursor.fetchall():
        s = (row[0] or "").lower()
        if s in dist:
            dist[s] = row[1]
    overview["sentiment_distribution"] = dist
    overview["total_analyzed"] = sum(dist.values())
    conn.close()
    return overview

@app.get("/api/market/sectors")
def get_sectors():
    return market_aggregator.get_sectors()

@app.get("/api/watchlist")
def get_watchlist():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker, company_name, sector, added_at, notes FROM watchlist ORDER BY added_at DESC")
    rows = cursor.fetchall()
    conn.close()
    
    items = []
    for r in rows:
        t = r["ticker"]
        quote = market_aggregator.get_quote(t)
        items.append({
            "ticker": t,
            "company_name": r["company_name"] or quote.get("company_name", t),
            "sector": r["sector"] or quote.get("sector", "Equities"),
            "added_at": r["added_at"],
            "notes": r["notes"],
            "quote": quote
        })
    return items

@app.post("/api/watchlist")
def add_to_watchlist(payload: WatchlistRequest):
    ticker = payload.ticker.strip().upper()
    quote = market_aggregator.get_quote(ticker)
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO watchlist (ticker, company_name, sector, added_at, notes)
    VALUES (?, ?, ?, ?, ?)
    """, (
        ticker,
        quote.get("company_name", ticker),
        quote.get("sector", "Equities"),
        datetime.now().isoformat(),
        payload.notes or ""
    ))
    conn.commit()
    conn.close()
    
    return {"status": "success", "message": f"{ticker} added to watchlist."}

@app.delete("/api/watchlist/{ticker}")
def remove_from_watchlist(ticker: str):
    clean_ticker = ticker.strip().upper()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM watchlist WHERE ticker = ?", (clean_ticker,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"{clean_ticker} removed from watchlist."}

@app.get("/api/analytics/accuracy")
def get_accuracy():
    return get_accuracy_metrics()


@app.get("/api/analytics/scope")
def get_scope_breakdown():
    """Aggregate analysis by news scope for the analytics dashboard."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT scope, COUNT(*) as count,
               AVG(sentiment_score) as avg_sentiment,
               SUM(CASE WHEN direction='UP' THEN 1 ELSE 0 END) as up_count,
               SUM(CASE WHEN direction='DOWN' THEN 1 ELSE 0 END) as down_count
        FROM analysis
        WHERE scope IS NOT NULL
        GROUP BY scope
        ORDER BY count DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return {
        "breakdown": [
            {
                "scope":         r["scope"],
                "count":         r["count"],
                "avg_sentiment": round(r["avg_sentiment"] or 0, 3),
                "up_count":      r["up_count"],
                "down_count":    r["down_count"],
            }
            for r in rows
        ],
        "compliance_disclaimer": MANDATORY_DISCLAIMER,
    }


@app.get("/api/analytics/categories")
def get_category_breakdown():
    """Aggregate analysis counts by 28-category taxonomy."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT event_type, event_display, COUNT(*) as count,
               AVG(confidence) as avg_confidence,
               AVG(sentiment_score) as avg_sentiment
        FROM analysis
        WHERE event_type IS NOT NULL
        GROUP BY event_type
        ORDER BY count DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return {
        "categories": [
            {
                "event_type":     r["event_type"],
                "event_display":  r["event_display"] or r["event_type"],
                "count":          r["count"],
                "avg_confidence": round(r["avg_confidence"] or 0, 1),
                "avg_sentiment":  round(r["avg_sentiment"] or 0, 3),
            }
            for r in rows
        ],
        "compliance_disclaimer": MANDATORY_DISCLAIMER,
    }


# ════════════════════════════════════════════════════════════════
# ML PIPELINE ROUTES
# ════════════════════════════════════════════════════════════════

@app.get("/api/ml/metrics")
def ml_metrics():
    """
    Return stored training metrics for all models × horizons.
    If insufficient data, returns message: 'Model requires more historical data for reliable training.'
    """
    data = get_model_metrics()
    return data


@app.post("/api/ml/train")
async def ml_train(background_tasks: BackgroundTasks):
    """
    Trigger full ML retraining pipeline (runs in background).
    Requires stock_price data — call /api/ml/collect-prices first.
    """
    def _run():
        results = train_all()
        return results
    background_tasks.add_task(_run)
    return {
        "status": "training_started",
        "message": "ML pipeline training started in background. Poll /api/ml/metrics for results.",
        "compliance_disclaimer": MANDATORY_DISCLAIMER,
    }


@app.post("/api/ml/collect-prices")
async def ml_collect_prices(background_tasks: BackgroundTasks):
    """
    Fetch and store 90-day OHLCV history for all tracked tickers.
    This provides the labeled data needed for ML training.
    """
    def _run():
        return fetch_and_store_prices()
    background_tasks.add_task(_run)
    return {
        "status": "collection_started",
        "message": "Stock price collection started. This may take 30-60 seconds.",
        "next_step": "After collection completes, call POST /api/ml/train to train models.",
    }


@app.get("/api/ml/predict/{article_id}")
def ml_predict_article(article_id: str):
    """
    Run ML inference on a specific article using all trained models.
    Returns ensemble vote + per-model probabilities per horizon.
    """
    conn = get_connection()
    row = conn.execute("""
        SELECT an.*, a.published_at FROM analysis an
        JOIN articles a ON an.article_id = a.id
        WHERE an.article_id = ?
    """, (article_id,)).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Article analysis not found")

    analysis_result = dict(row)
    predictions = predict_article(analysis_result, analysis_result.get("published_at", ""))

    if not predictions:
        return {
            "article_id": article_id,
            "predictions": {},
            "message": "Models not yet trained. Call POST /api/ml/collect-prices then POST /api/ml/train.",
            "compliance_disclaimer": MANDATORY_DISCLAIMER,
        }

    return {
        "article_id":  article_id,
        "ticker":      analysis_result.get("ticker"),
        "predictions": predictions,
        "compliance_disclaimer": MANDATORY_DISCLAIMER,
    }


@app.get("/api/ml/status")
def ml_status():
    """Quick status check: how many stock_price rows, analysis rows, model files."""
    import os
    conn = get_connection()
    n_prices   = conn.execute("SELECT COUNT(*) FROM stock_price").fetchone()[0]
    n_analysis = conn.execute("SELECT COUNT(*) FROM analysis").fetchone()[0]
    n_tickers  = conn.execute("SELECT COUNT(DISTINCT ticker) FROM stock_price").fetchone()[0]
    n_metrics  = conn.execute("SELECT COUNT(*) FROM model_metric WHERE is_sufficient=1").fetchone()[0]
    conn.close()

    from ml_pipeline import MODEL_DIR, MIN_SAMPLES, MODELS
    model_files = [f for f in os.listdir(MODEL_DIR) if f.endswith(".joblib")] if os.path.isdir(MODEL_DIR) else []

    ready = n_prices >= MIN_SAMPLES and n_analysis >= MIN_SAMPLES
    return {
        "stock_price_rows":   n_prices,
        "analysis_rows":      n_analysis,
        "unique_tickers":     n_tickers,
        "trained_models":     len(model_files),
        "sufficient_metrics": n_metrics,
        "ready_to_train":     ready,
        "min_samples_required": MIN_SAMPLES,
        "message": (
            "Ready to train — call POST /api/ml/train" if ready
            else f"Need >= {MIN_SAMPLES} labeled price rows. Call POST /api/ml/collect-prices first."
        ),
        "compliance_disclaimer": MANDATORY_DISCLAIMER,
    }


@app.get("/api/ml/stock-prices/{ticker}")
def get_stock_prices(ticker: str, days: int = Query(30, ge=1, le=365)):
    """Return stored OHLCV data for a ticker (for chart display)."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT date, open, high, low, close, volume
        FROM stock_price WHERE ticker=?
        ORDER BY date DESC LIMIT ?
    """, (ticker.upper(), days)).fetchall()
    conn.close()
    return {
        "ticker": ticker.upper(),
        "prices": [dict(r) for r in reversed(rows)],
        "count":  len(rows),
    }


@app.get("/api/ml/dataset/download")
def download_dataset():
    """Download the consolidated ML training dataset as CSV."""
    import os
    if not os.path.exists(DATASET_CSV_PATH):
        export_dataset()
    if not os.path.exists(DATASET_CSV_PATH):
        raise HTTPException(status_code=404, detail="Dataset not yet generated")
    return FileResponse(
        DATASET_CSV_PATH,
        media_type="text/csv",
        filename="market_news_ml_dataset.csv"
    )


@app.get("/api/ml/dataset/info")
def dataset_info():
    """Get statistics, column schema, and sample rows for the training dataset."""
    import os
    if not os.path.exists(DATASET_CSV_PATH):
        export_dataset()
    import pandas as pd
    try:
        df = pd.read_csv(DATASET_CSV_PATH)
        return {
            "file_path": DATASET_CSV_PATH,
            "total_records": len(df),
            "labeled_1d": int((df["label_1d"] != "UNLABELED").sum()),
            "labeled_3d": int((df["label_3d"] != "UNLABELED").sum()),
            "labeled_5d": int((df["label_5d"] != "UNLABELED").sum()),
            "distribution_1d": df["label_1d"].value_counts().to_dict(),
            "distribution_3d": df["label_3d"].value_counts().to_dict(),
            "distribution_5d": df["label_5d"].value_counts().to_dict(),
            "unique_tickers": int(df["ticker"].nunique()),
            "columns": list(df.columns),
            "download_url": "http://127.0.0.1:8000/api/ml/dataset/download",
            "compliance_disclaimer": MANDATORY_DISCLAIMER,
        }
    except Exception as e:
        return {"error": str(e)}


# ════════════════════════════════════════════════════════════════
# INDIAN STOCKS AUTOCOMPLETE & MASTER SEARCH
# ════════════════════════════════════════════════════════════════

@app.get("/api/stocks/search")
def search_indian_stocks(
    q: str = Query("", description="Company name, ticker, or alias"),
    limit: int = Query(8, ge=1, le=20)
):
    """
    Fast autocomplete endpoint for Indian stocks (NSE/BSE).
    Searches ticker, company name, aliases, and fuzzy typos.
    Enriched with live/cached current price in INR (₹) and day change.
    """
    matches = stock_master_index.search(q, limit=limit)
    enriched = stock_master_index.enrich_with_quotes(matches, market_aggregator)
    return {
        "query": q,
        "count": len(enriched),
        "results": enriched,
        "compliance_disclaimer": MANDATORY_DISCLAIMER
    }


@app.get("/api/stocks/master")
def get_master_stocks_summary():
    """Return count and summary of indexed Indian stocks."""
    return {
        "total_indexed": len(stock_master_index.stocks),
        "exchange": "NSE / BSE (India)",
        "compliance_disclaimer": MANDATORY_DISCLAIMER
    }


@app.get("/api/stocks/price-brackets")
def get_stocks_by_price_brackets():
    """
    Returns Indian shares divided into 3 distinct price groups:
    1. UNDER_500   : ₹0 to ₹500      (Affordable, Small & Mid-Cap)
    2. 500_TO_2000 : ₹500 to ₹2,000  (Core, Mainstream Momentum)
    3. ABOVE_2000  : ₹2,000+         (Heavyweights & Bluechips)
    Enriched with current share price, day change %, sector, and matching news count.
    """
    conn = get_connection()
    news_rows = conn.execute("""
        SELECT an.ticker, an.sentiment, an.impact_level, COUNT(*) as c
        FROM analysis an
        WHERE an.ticker IS NOT NULL
        GROUP BY an.ticker
    """).fetchall()
    conn.close()

    news_map = {}
    for r in news_rows:
        t = r["ticker"]
        news_map[t] = {
            "count": r["c"],
            "sentiment": r["sentiment"],
            "impact_level": r["impact_level"]
        }

    groups = {
        "UNDER_500": {
            "id": "UNDER_500",
            "title": "₹0 to ₹500",
            "subtitle": "Affordable, Small & Mid-Cap Equities",
            "range_label": "₹0 – ₹500",
            "badge_color": "#059669",
            "badge_bg": "#ECFDF5",
            "badge_border": "#A7F3D0",
            "stocks": []
        },
        "500_TO_2000": {
            "id": "500_TO_2000",
            "title": "₹500 to ₹2,000",
            "subtitle": "Core Mainstream & Growth Equities",
            "range_label": "₹500 – ₹2,000",
            "badge_color": "#2563EB",
            "badge_bg": "#EFF6FF",
            "badge_border": "#BFDBFE",
            "stocks": []
        },
        "ABOVE_2000": {
            "id": "ABOVE_2000",
            "title": "₹2,000+",
            "subtitle": "Bluechip Heavyweights & High-Value Leaders",
            "range_label": "₹2,000+",
            "badge_color": "#7C3AED",
            "badge_bg": "#F5F3FF",
            "badge_border": "#DDD6FE",
            "stocks": []
        }
    }

    from indian_stocks_master import INDIAN_STOCKS_DATA
    for s in INDIAN_STOCKS_DATA:
        t = s["ticker"]
        if t.startswith("^"):
            continue
        pinfo = get_stock_price_info(t)
        b_id = pinfo["bracket_id"]
        if b_id in groups:
            n_data = news_map.get(t, {"count": 0, "sentiment": "Neutral", "impact_level": "LOW"})
            groups[b_id]["stocks"].append({
                "ticker": t,
                "symbol": s["symbol"],
                "name": s["name"],
                "sector": s.get("sector", "Equities"),
                "price": pinfo["price"],
                "change_pct": pinfo["change_pct"],
                "bracket_id": b_id,
                "news_count": n_data["count"],
                "sentiment": n_data["sentiment"],
                "impact_level": n_data["impact_level"]
            })

    # Sort each group: active news catalyst first, then price
    for b_id in groups:
        groups[b_id]["stocks"].sort(key=lambda x: (x["news_count"] > 0, x["news_count"], x["price"] or 0), reverse=True)

    return {
        "groups": groups,
        "compliance_disclaimer": MANDATORY_DISCLAIMER
    }


# ════════════════════════════════════════════════════════════════
# ANALYTICAL TRADE ENGINE  (ATR · EMA · RSI · Pivot S/R)
# ════════════════════════════════════════════════════════════════

@app.get("/api/stocks/trade-analysis/{ticker}")
def get_trade_analysis(
    ticker: str,
    direction: str = Query("NEUTRAL", description="NLP direction: UP | DOWN | NEUTRAL"),
    confidence: float = Query(70.0, ge=0, le=100),
    sentiment_score: float = Query(0.5, ge=-1.0, le=1.0),
    event_type: str = Query("", description="Event type from NLP engine (e.g. EARNINGS, RBI_ANNOUNCEMENT)")
):
    """
    Compute data-driven, analytical trade guidance for an Indian stock.

    This endpoint uses REAL 90-day OHLCV data to compute:
    - ATR-14 based stop-loss (not random multiplier)
    - EMA-20 / EMA-50 for trend alignment
    - RSI-14 for momentum and overbought/oversold detection
    - Swing Pivot Support & Resistance from actual price history
    - Precise buy zone, target 1, target 2 anchored to real levels
    - NLP sentiment + technical alignment conviction score
    """
    clean_ticker = ticker.strip().upper()
    result = compute_trade_analysis(
        ticker=clean_ticker,
        direction=direction.upper(),
        confidence=confidence,
        sentiment_score=sentiment_score,
        event_type=event_type.upper()
    )
    result["compliance_disclaimer"] = MANDATORY_DISCLAIMER
    return result
